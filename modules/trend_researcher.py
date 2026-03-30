import json
import os
import subprocess
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

RESEARCH_PROMPT = """You are a blog keyword researcher. Your job is to find trending AI topics that everyday people (non-tech) are searching for right now.

Research what's trending in the last 7-30 days about AI being used in everyday life. Focus on these categories: {categories}

Use web search to find:
1. What questions people are asking about AI on Reddit, Quora, forums
2. What AI tools or features launched recently that affect daily life
3. What "AI + everyday task" topics are getting attention on social media
4. Google autocomplete suggestions for "AI for [everyday task]"

For each topic you find, evaluate:
- **Search demand**: Are real people searching for this? (high/medium/low)
- **Competition**: How many quality articles already exist? (high/medium/low)
- **Content angle**: What's the best angle — how-to guide, tool comparison, or tips list?

IMPORTANT: Avoid these already-published keywords: {posted_keywords}

Return ONLY a valid JSON array (no markdown, no commentary, no code fences) with exactly {max_keywords} items:
[
  {{
    "keyword": "the exact search-friendly keyword phrase",
    "category": "one of the categories listed above",
    "interest": 80,
    "search_demand": "high",
    "competition": "low",
    "related_queries": ["related search term 1", "related search term 2", "related search term 3"],
    "content_angle": "howto or tools or tips",
    "reasoning": "why this keyword is a good pick right now"
  }}
]

interest should be 1-100 (your estimate of relative search interest).
Prioritize: high demand + low competition + timely/trending topics.
"""


class TrendResearcher:
    def __init__(self, config: dict, output_dir: str, posted_keywords_path: str):
        self.config = config
        self.output_dir = output_dir
        self.posted_keywords_path = posted_keywords_path
        self.trends_config = config["trends"]
        self.categories = config["content"]["categories"]
        self.claude_timeout = config.get("claude", {}).get("timeout_seconds", 300)

    def _get_posted_keywords(self) -> list[str]:
        if not os.path.exists(self.posted_keywords_path):
            return []
        with open(self.posted_keywords_path) as f:
            return json.load(f)

    def _build_research_prompt(self) -> str:
        posted = self._get_posted_keywords()
        posted_str = ", ".join(posted) if posted else "none yet"
        categories_str = ", ".join(self.categories)
        max_kw = self.trends_config["max_keywords_per_run"]

        return RESEARCH_PROMPT.format(
            categories=categories_str,
            posted_keywords=posted_str,
            max_keywords=max_kw,
        )

    def _call_claude(self, prompt: str) -> str:
        result = subprocess.run(
            [
                "claude", "-p", "-",
                "--output-format", "text",
                "--allowedTools", "WebSearch,WebFetch",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=self.claude_timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")
        return result.stdout.strip()

    def _parse_keywords(self, raw: str) -> list[dict]:
        """Extract JSON array from Claude's response."""
        # Try direct parse first
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code fences
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding array brackets
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        logger.error(f"Failed to parse keywords from Claude response: {raw[:500]}")
        return []

    def _normalize_keywords(self, keywords: list[dict]) -> list[dict]:
        """Normalize and score parsed keywords."""
        posted = self._get_posted_keywords()
        normalized = []

        for kw in keywords:
            keyword = kw.get("keyword", "").strip()
            if not keyword or keyword in posted:
                continue

            # Map content_angle to template
            angle = kw.get("content_angle", "tips").lower()
            if angle in ("howto", "how-to", "how to", "guide"):
                template = "howto_apply"
            elif angle in ("tools", "best", "comparison", "list"):
                template = "best_tools"
            else:
                template = "daily_ai_tips"

            # Score: high demand + low competition = best
            demand_map = {"high": 3, "medium": 2, "low": 1}
            competition_map = {"low": 3, "medium": 2, "high": 1}
            demand = demand_map.get(kw.get("search_demand", "medium"), 2)
            competition = competition_map.get(kw.get("competition", "medium"), 2)
            interest = kw.get("interest", 50)
            score = round((interest / 100) * demand * competition, 2)

            normalized.append({
                "keyword": keyword,
                "category": kw.get("category", "general"),
                "interest": interest,
                "search_demand": kw.get("search_demand", "medium"),
                "competition": kw.get("competition", "medium"),
                "related_queries": kw.get("related_queries", [])[:5],
                "template": template,
                "reasoning": kw.get("reasoning", ""),
                "score": score,
            })

        normalized.sort(key=lambda x: x["score"], reverse=True)
        return normalized

    def _enrich_keywords(self, keywords: list[dict]) -> list[dict]:
        """Add title_suggestion based on template."""
        for kw in keywords:
            keyword = kw["keyword"]

            # If keyword is already a full phrase (e.g. "how to use AI for meal planning"),
            # use it directly as the title instead of wrapping in a template
            kw_lower = keyword.lower()
            is_full_phrase = any(kw_lower.startswith(p) for p in [
                "how to", "best ", "top ", "why ", "what ",
            ])

            if is_full_phrase:
                # Capitalize as a title, add suffix
                kw["title_suggestion"] = keyword.title() + " — A Simple Guide"
            elif kw["template"] == "howto_apply":
                clean = re.sub(r"^AI\s+", "", keyword, flags=re.IGNORECASE)
                kw["title_suggestion"] = f"How to Use AI for {clean.title()} — A Beginner's Guide"
            elif kw["template"] == "best_tools":
                clean = re.sub(r"^AI\s+", "", keyword, flags=re.IGNORECASE)
                kw["title_suggestion"] = f"Best Free AI Tools for {clean.title()} in {datetime.now().year}"
            else:
                clean = re.sub(r"^AI\s+", "", keyword, flags=re.IGNORECASE)
                kw["title_suggestion"] = f"5 Easy Ways AI Can Help You With {clean.title()}"
        return keywords

    def _load_cached_keywords(self) -> list[dict]:
        """Load keywords from previous runs as fallback."""
        if not os.path.exists(self.output_dir):
            return []

        posted = self._get_posted_keywords()
        cached = []
        for f in sorted(os.listdir(self.output_dir), reverse=True):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(self.output_dir, f)) as fh:
                        items = json.load(fh)
                        for item in items:
                            if item.get("keyword") not in posted:
                                cached.append(item)
                except (json.JSONDecodeError, IOError):
                    continue
        return cached

    def run(self) -> str:
        os.makedirs(self.output_dir, exist_ok=True)
        max_kw = self.trends_config["max_keywords_per_run"]

        # Primary: Claude CLI research
        try:
            prompt = self._build_research_prompt()
            logger.info("Researching trending keywords via Claude CLI...")
            raw = self._call_claude(prompt)
            parsed = self._parse_keywords(raw)
            keywords = self._normalize_keywords(parsed)
            top_keywords = keywords[:max_kw]
        except Exception as e:
            logger.error(f"Claude research failed: {e}")
            top_keywords = []

        # Fallback: cached keywords
        if not top_keywords:
            logger.warning("No fresh keywords. Falling back to cached keywords.")
            cached = self._load_cached_keywords()
            top_keywords = cached[:max_kw]

        top_keywords = self._enrich_keywords(top_keywords)

        date_str = datetime.now().strftime("%Y-%m-%d")
        output_path = os.path.join(self.output_dir, f"{date_str}.json")
        with open(output_path, "w") as f:
            json.dump(top_keywords, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(top_keywords)} keywords to {output_path}")
        return output_path
