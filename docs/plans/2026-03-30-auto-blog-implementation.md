# Auto Blog Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Blogger에 AI 일상 활용법 콘텐츠를 자동 생성/업로드하는 파이프라인을 구축한다.

**Architecture:** 4개 모듈(trend_researcher, content_generator, blogger_uploader, orchestrator)로 분리된 파이프라인. 크론잡이 매일 orchestrator를 실행하고, orchestrator가 확률적으로 포스팅 여부를 결정한 뒤 리서치 → 생성 → 업로드를 순차 실행한다.

**Tech Stack:** Python 3.11+, pytrends (Google Trends), Claude Code CLI, google-api-python-client (Blogger API v3), python-markdown, PyYAML, pytest

**Spec:** `docs/specs/2026-03-30-auto-blog-design.md`

---

## File Map

```
auto-blog/
├── config.example.yaml          # 설정 템플릿 (git 추적)
├── config.yaml                  # 실제 설정 (gitignore)
├── requirements.txt             # 의존성
├── .gitignore
├── setup_auth.py                # Blogger OAuth 최초 인증
├── orchestrator.py              # 메인 파이프라인 실행기
├── modules/
│   ├── __init__.py
│   ├── trend_researcher.py      # Google Trends 키워드 수집
│   ├── content_generator.py     # Claude Code CLI로 글 생성
│   └── blogger_uploader.py      # Blogger API v3 업로드
├── prompts/
│   ├── howto_apply.md           # How-to 가이드 프롬프트
│   ├── best_tools.md            # Best tools 리스트 프롬프트
│   └── daily_ai_tips.md         # AI 팁 프롬프트
├── output/
│   ├── keywords/                # 키워드 JSON 산출물
│   └── drafts/                  # 생성된 글 Markdown
├── data/
│   └── posted_keywords.json     # 게시 완료 키워드 추적
├── logs/                        # 실행 로그
├── credentials/                 # OAuth 토큰 (gitignore)
└── tests/
    ├── __init__.py
    ├── test_trend_researcher.py
    ├── test_content_generator.py
    ├── test_blogger_uploader.py
    └── test_orchestrator.py
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `config.example.yaml`
- Create: `modules/__init__.py`
- Create: `tests/__init__.py`
- Create: `data/posted_keywords.json`

- [ ] **Step 1: Create requirements.txt**

```txt
pytrends==4.9.2
google-api-python-client==2.131.0
google-auth-oauthlib==1.2.0
google-auth-httplib2==0.2.0
markdown==3.6
PyYAML==6.0.1
pytest==8.2.0
```

- [ ] **Step 2: Create .gitignore**

```
config.yaml
credentials/
output/
logs/
__pycache__/
*.pyc
.pytest_cache/
venv/
```

- [ ] **Step 3: Create config.example.yaml**

```yaml
blogger:
  blog_id: "YOUR_BLOG_ID"
  credentials_path: "credentials/google_oauth.json"
  token_path: "credentials/token.json"

schedule:
  posts_per_week: [3, 4]
  time_range_hours: [6, 22]
  random_delay_max_hours: 2

content:
  language: "en"
  min_word_count: 800
  target_audience: "non-tech adults"
  tone: "friendly, practical, data-driven"
  categories:
    - cooking
    - travel
    - health
    - finance
    - parenting
    - shopping
    - productivity
    - education
    - fitness
    - home
    - career
    - hobbies

trends:
  region: "US"
  lookback_days: 7
  max_keywords_per_run: 3

claude:
  timeout_seconds: 120
  max_retries: 1
```

- [ ] **Step 4: Create empty init files and data file**

`modules/__init__.py` — empty file
`tests/__init__.py` — empty file

`data/posted_keywords.json`:
```json
[]
```

- [ ] **Step 5: Create output and log directories**

```bash
mkdir -p output/keywords output/drafts logs credentials
```

- [ ] **Step 6: Commit**

```bash
git init
git add requirements.txt .gitignore config.example.yaml modules/__init__.py tests/__init__.py data/posted_keywords.json
git commit -m "chore: scaffold project structure"
```

---

## Task 2: Trend Researcher

**Files:**
- Create: `modules/trend_researcher.py`
- Create: `tests/test_trend_researcher.py`

- [ ] **Step 1: Write failing tests**

`tests/test_trend_researcher.py`:
```python
import json
import os
import pytest
from unittest.mock import patch, MagicMock
from modules.trend_researcher import TrendResearcher


@pytest.fixture
def researcher(tmp_path):
    config = {
        "trends": {
            "region": "US",
            "lookback_days": 7,
            "max_keywords_per_run": 3,
        },
        "content": {
            "categories": ["cooking", "travel", "fitness"],
        },
    }
    return TrendResearcher(
        config=config,
        output_dir=str(tmp_path / "keywords"),
        posted_keywords_path=str(tmp_path / "posted.json"),
    )


@pytest.fixture(autouse=True)
def setup_dirs(researcher, tmp_path):
    os.makedirs(tmp_path / "keywords", exist_ok=True)
    with open(tmp_path / "posted.json", "w") as f:
        json.dump([], f)


class TestBuildQueries:
    def test_combines_ai_with_categories(self, researcher):
        queries = researcher.build_queries()
        assert "AI cooking" in queries
        assert "AI travel" in queries
        assert "AI fitness" in queries

    def test_number_of_queries_matches_categories(self, researcher):
        queries = researcher.build_queries()
        assert len(queries) == 3


class TestScoreKeywords:
    def test_scores_and_sorts_by_score_desc(self, researcher):
        raw_data = [
            {"keyword": "AI cooking", "interest": 80, "result_count": 1000},
            {"keyword": "AI travel", "interest": 90, "result_count": 500},
        ]
        scored = researcher.score_keywords(raw_data)
        assert scored[0]["keyword"] == "AI travel"
        assert "score" in scored[0]

    def test_filters_already_posted(self, researcher, tmp_path):
        with open(tmp_path / "posted.json", "w") as f:
            json.dump(["AI cooking"], f)
        raw_data = [
            {"keyword": "AI cooking", "interest": 80, "result_count": 1000},
            {"keyword": "AI travel", "interest": 90, "result_count": 500},
        ]
        scored = researcher.score_keywords(raw_data)
        assert len(scored) == 1
        assert scored[0]["keyword"] == "AI travel"


class TestSelectTemplate:
    def test_howto_query(self, researcher):
        assert researcher.select_template("how to use AI for cooking") == "howto_apply"

    def test_best_query(self, researcher):
        assert researcher.select_template("best AI tools for travel") == "best_tools"

    def test_default_query(self, researcher):
        assert researcher.select_template("AI cooking tips") == "daily_ai_tips"


class TestFetchTrends:
    @patch("modules.trend_researcher.TrendReq")
    def test_returns_keyword_data(self, mock_trendreq_cls, researcher):
        mock_pytrends = MagicMock()
        mock_trendreq_cls.return_value = mock_pytrends

        import pandas as pd

        mock_pytrends.interest_over_time.return_value = pd.DataFrame(
            {"AI cooking": [50, 60, 80]},
        )
        mock_pytrends.related_queries.return_value = {
            "AI cooking": {
                "top": pd.DataFrame({"query": ["ChatGPT recipes", "AI meal planner"]}),
            }
        }

        results = researcher.fetch_trends(["AI cooking"])
        assert len(results) >= 1
        assert results[0]["keyword"] == "AI cooking"
        assert "interest" in results[0]
        assert "related_queries" in results[0]


class TestRun:
    @patch.object(TrendResearcher, "fetch_trends")
    def test_run_saves_json(self, mock_fetch, researcher, tmp_path):
        mock_fetch.return_value = [
            {
                "keyword": "AI meal planning",
                "interest": 82,
                "result_count": 500,
                "related_queries": ["ChatGPT meal prep"],
            },
        ]
        result_path = researcher.run()
        assert os.path.exists(result_path)
        with open(result_path) as f:
            data = json.load(f)
        assert len(data) >= 1
        assert data[0]["keyword"] == "AI meal planning"
        assert "template" in data[0]
        assert "score" in data[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/imchangi/SipeProjects/auto-blog && python -m pytest tests/test_trend_researcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.trend_researcher'`

- [ ] **Step 3: Implement trend_researcher.py**

`modules/trend_researcher.py`:
```python
import json
import os
import time
import random
import logging
from datetime import datetime, timedelta

from pytrends.request import TrendReq

logger = logging.getLogger(__name__)


class TrendResearcher:
    def __init__(self, config: dict, output_dir: str, posted_keywords_path: str):
        self.config = config
        self.output_dir = output_dir
        self.posted_keywords_path = posted_keywords_path
        self.trends_config = config["trends"]
        self.categories = config["content"]["categories"]

    def build_queries(self) -> list[str]:
        return [f"AI {cat}" for cat in self.categories]

    def fetch_trends(self, queries: list[str]) -> list[dict]:
        pytrends = TrendReq(hl="en-US", tz=360)
        results = []

        for query in queries:
            time.sleep(random.uniform(2, 5))
            try:
                pytrends.build_payload(
                    [query],
                    timeframe=f"now {self.trends_config['lookback_days']}-d",
                    geo=self.trends_config["region"],
                )
                interest_df = pytrends.interest_over_time()
                if interest_df.empty:
                    continue

                interest = int(interest_df[query].mean())

                related = pytrends.related_queries()
                related_queries = []
                if query in related and related[query]["top"] is not None:
                    related_queries = related[query]["top"]["query"].tolist()[:5]

                results.append({
                    "keyword": query,
                    "interest": interest,
                    "result_count": len(related_queries) * 100 + 1,
                    "related_queries": related_queries,
                })
            except Exception as e:
                logger.warning(f"Failed to fetch trends for '{query}': {e}")
                continue

        return results

    def score_keywords(self, raw_data: list[dict]) -> list[dict]:
        with open(self.posted_keywords_path) as f:
            posted = json.load(f)

        scored = []
        for item in raw_data:
            if item["keyword"] in posted:
                continue
            interest = item["interest"]
            competition = item["result_count"]
            score = interest / (competition + 1)
            scored.append({**item, "score": round(score, 4)})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    def select_template(self, keyword: str) -> str:
        kw = keyword.lower()
        if kw.startswith("how to") or "how to" in kw:
            return "howto_apply"
        if kw.startswith("best") or "best" in kw or "top" in kw:
            return "best_tools"
        return "daily_ai_tips"

    def run(self) -> str:
        os.makedirs(self.output_dir, exist_ok=True)
        queries = self.build_queries()
        raw_data = self.fetch_trends(queries)
        scored = self.score_keywords(raw_data)

        max_kw = self.trends_config["max_keywords_per_run"]
        top_keywords = scored[:max_kw]

        for kw in top_keywords:
            kw["template"] = self.select_template(kw["keyword"])
            title_keyword = kw["keyword"].replace("AI ", "")
            if kw["template"] == "howto_apply":
                kw["title_suggestion"] = f"How to Use AI for {title_keyword.title()} — A Simple Guide for Beginners"
            elif kw["template"] == "best_tools":
                kw["title_suggestion"] = f"Best Free AI Tools for {title_keyword.title()} in 2026"
            else:
                kw["title_suggestion"] = f"5 Easy Ways AI Can Help You With {title_keyword.title()}"

        date_str = datetime.now().strftime("%Y-%m-%d")
        output_path = os.path.join(self.output_dir, f"{date_str}.json")
        with open(output_path, "w") as f:
            json.dump(top_keywords, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(top_keywords)} keywords to {output_path}")
        return output_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/imchangi/SipeProjects/auto-blog && python -m pytest tests/test_trend_researcher.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add modules/trend_researcher.py tests/test_trend_researcher.py
git commit -m "feat: add trend researcher module with Google Trends integration"
```

---

## Task 3: Content Generator

**Files:**
- Create: `modules/content_generator.py`
- Create: `tests/test_content_generator.py`
- Create: `prompts/howto_apply.md`
- Create: `prompts/best_tools.md`
- Create: `prompts/daily_ai_tips.md`

- [ ] **Step 1: Create prompt templates**

`prompts/howto_apply.md`:
```markdown
You are a friendly tech blogger writing for people who are NOT tech-savvy. Write a practical how-to guide in English.

**Topic:** How to use AI for {{keyword}}
**Title:** {{title}}
**Target audience:** Adults who are not familiar with technology. They search Google for answers. Explain everything simply.
**Tone:** Warm, encouraging, practical. Like a helpful friend explaining things over coffee.

**Requirements:**
- Start with a short introduction explaining why this matters in everyday life (2-3 sentences)
- Use simple, jargon-free language. If you must use a technical term, explain it immediately
- Include specific tool names (ChatGPT, Google Gemini, etc.) with step-by-step instructions
- Each step should have a concrete example with actual input/output
- Include at least one real statistic or data point to support the value
- End with a brief summary of key takeaways

**SEO Requirements:**
- Use the keyword "{{keyword}}" naturally in the first paragraph and at least 2 subheadings
- Include these related terms naturally: {{related_queries}}
- Write a meta description (under 160 characters) at the very top in this format: `META: your description here`
- Use H2 (##) for main sections, H3 (###) for subsections

**US Targeting:**
- Write in American English (color, not colour; favorite, not favourite)
- Use USD for prices, MM/DD/YYYY for dates
- Reference US-based services and examples
- Assume the reader is in the United States

**Format:** Markdown. Minimum 800 words. Do NOT include any AI disclosure or "as an AI" language.
```

`prompts/best_tools.md`:
```markdown
You are a friendly tech blogger writing for people who are NOT tech-savvy. Write a practical listicle in English.

**Topic:** Best free AI tools for {{keyword}}
**Title:** {{title}}
**Target audience:** Adults who are not familiar with technology. They search Google for answers. Explain everything simply.
**Tone:** Warm, encouraging, practical. Like a helpful friend explaining things over coffee.

**Requirements:**
- List 5-7 free (or freemium) AI tools
- For each tool: name, what it does in one sentence, step-by-step how to use it, one specific example, pricing (free tier details)
- Rank from easiest to most feature-rich
- Include a comparison table at the end (tool name, best for, price, difficulty)
- Include at least one real statistic or data point
- End with "Which one should you try first?" recommendation

**SEO Requirements:**
- Use the keyword "{{keyword}}" naturally in the first paragraph and at least 2 subheadings
- Include these related terms naturally: {{related_queries}}
- Write a meta description (under 160 characters) at the very top in this format: `META: your description here`
- Use H2 (##) for main sections, H3 (###) for subsections

**US Targeting:**
- Write in American English (color, not colour; favorite, not favourite)
- Use USD for prices, MM/DD/YYYY for dates
- Reference US-based services and examples
- Assume the reader is in the United States

**Format:** Markdown. Minimum 800 words. Do NOT include any AI disclosure or "as an AI" language.
```

`prompts/daily_ai_tips.md`:
```markdown
You are a friendly tech blogger writing for people who are NOT tech-savvy. Write a practical tips article in English.

**Topic:** Easy ways AI can help you with {{keyword}}
**Title:** {{title}}
**Target audience:** Adults who are not familiar with technology. They search Google for answers. Explain everything simply.
**Tone:** Warm, encouraging, practical. Like a helpful friend explaining things over coffee.

**Requirements:**
- Present 5 practical, everyday tips
- Each tip: clear heading, why it helps, which tool to use, step-by-step example
- Start from the simplest tip and progress to slightly more advanced
- Include specific numbers or data (e.g., "saves an average of 30 minutes per week")
- Include a "Getting Started" section at the end with the single easiest first step
- Each tip should be independent — readers can try any single tip on its own

**SEO Requirements:**
- Use the keyword "{{keyword}}" naturally in the first paragraph and at least 2 subheadings
- Include these related terms naturally: {{related_queries}}
- Write a meta description (under 160 characters) at the very top in this format: `META: your description here`
- Use H2 (##) for main sections, H3 (###) for subsections

**US Targeting:**
- Write in American English (color, not colour; favorite, not favourite)
- Use USD for prices, MM/DD/YYYY for dates
- Reference US-based services and examples
- Assume the reader is in the United States

**Format:** Markdown. Minimum 800 words. Do NOT include any AI disclosure or "as an AI" language.
```

- [ ] **Step 2: Write failing tests**

`tests/test_content_generator.py`:
```python
import json
import os
import pytest
from unittest.mock import patch, MagicMock
from modules.content_generator import ContentGenerator


@pytest.fixture
def generator(tmp_path):
    config = {
        "claude": {
            "timeout_seconds": 120,
            "max_retries": 1,
        },
        "content": {
            "min_word_count": 800,
        },
    }
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    (prompts_dir / "howto_apply.md").write_text(
        "Write about {{keyword}}. Title: {{title}}. Related: {{related_queries}}"
    )
    (prompts_dir / "best_tools.md").write_text(
        "Best tools for {{keyword}}. Title: {{title}}. Related: {{related_queries}}"
    )
    (prompts_dir / "daily_ai_tips.md").write_text(
        "Tips about {{keyword}}. Title: {{title}}. Related: {{related_queries}}"
    )

    return ContentGenerator(
        config=config,
        prompts_dir=str(prompts_dir),
        output_dir=str(tmp_path / "drafts"),
    )


@pytest.fixture
def sample_keyword():
    return {
        "keyword": "AI meal planning",
        "category": "cooking",
        "template": "howto_apply",
        "title_suggestion": "How to Use AI for Meal Planning",
        "related_queries": ["ChatGPT meal prep", "AI diet planner"],
        "score": 0.15,
    }


class TestAssemblePrompt:
    def test_injects_keyword_and_title(self, generator, sample_keyword):
        prompt = generator.assemble_prompt(sample_keyword)
        assert "AI meal planning" in prompt
        assert "How to Use AI for Meal Planning" in prompt

    def test_injects_related_queries(self, generator, sample_keyword):
        prompt = generator.assemble_prompt(sample_keyword)
        assert "ChatGPT meal prep" in prompt

    def test_uses_correct_template(self, generator, sample_keyword):
        prompt = generator.assemble_prompt(sample_keyword)
        assert "Write about" in prompt


class TestValidateDraft:
    def test_passes_valid_draft(self, generator):
        draft = "# Title\n\n## Section 1\n\n" + "word " * 800 + "\n\n## Section 2\n\nMore content."
        assert generator.validate_draft(draft) is True

    def test_fails_short_draft(self, generator):
        draft = "# Title\n\n## Section\n\nToo short."
        assert generator.validate_draft(draft) is False

    def test_fails_no_heading(self, generator):
        draft = "word " * 900
        assert generator.validate_draft(draft) is False


class TestGenerate:
    @patch("modules.content_generator.subprocess.run")
    def test_calls_claude_cli_and_saves_draft(self, mock_run, generator, sample_keyword, tmp_path):
        fake_article = "# How to Use AI for Meal Planning\n\n## Introduction\n\n" + "word " * 800 + "\n\n## Getting Started\n\nMore content."
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=fake_article,
        )
        result_path = generator.generate(sample_keyword, "2026-03-30")
        assert os.path.exists(result_path)
        with open(result_path) as f:
            content = f.read()
        assert "Meal Planning" in content

    @patch("modules.content_generator.subprocess.run")
    def test_retries_on_validation_failure(self, mock_run, generator, sample_keyword):
        short_article = "Too short."
        good_article = "# Title\n\n## Section 1\n\n" + "word " * 800 + "\n\n## Section 2\n\nDone."
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=short_article),
            MagicMock(returncode=0, stdout=good_article),
        ]
        result_path = generator.generate(sample_keyword, "2026-03-30")
        assert result_path is not None
        assert mock_run.call_count == 2
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/imchangi/SipeProjects/auto-blog && python -m pytest tests/test_content_generator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.content_generator'`

- [ ] **Step 4: Implement content_generator.py**

`modules/content_generator.py`:
```python
import os
import subprocess
import logging
import re

logger = logging.getLogger(__name__)


class ContentGenerator:
    def __init__(self, config: dict, prompts_dir: str, output_dir: str):
        self.config = config
        self.prompts_dir = prompts_dir
        self.output_dir = output_dir
        self.claude_config = config["claude"]
        self.min_word_count = config["content"]["min_word_count"]

    def assemble_prompt(self, keyword_data: dict) -> str:
        template_name = keyword_data["template"]
        template_path = os.path.join(self.prompts_dir, f"{template_name}.md")

        with open(template_path) as f:
            template = f.read()

        related_str = ", ".join(keyword_data.get("related_queries", []))

        prompt = template.replace("{{keyword}}", keyword_data["keyword"])
        prompt = prompt.replace("{{title}}", keyword_data["title_suggestion"])
        prompt = prompt.replace("{{related_queries}}", related_str)

        return prompt

    def validate_draft(self, draft: str) -> bool:
        word_count = len(draft.split())
        if word_count < self.min_word_count:
            logger.warning(f"Draft too short: {word_count} words (min {self.min_word_count})")
            return False

        has_h1_or_h2 = bool(re.search(r"^#{1,2}\s+.+", draft, re.MULTILINE))
        if not has_h1_or_h2:
            logger.warning("Draft missing headings")
            return False

        h2_count = len(re.findall(r"^##\s+.+", draft, re.MULTILINE))
        if h2_count < 2:
            logger.warning(f"Draft has only {h2_count} H2 headings (min 2)")
            return False

        return True

    def call_claude(self, prompt: str) -> str:
        timeout = self.claude_config["timeout_seconds"]
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text", "--max-turns", "1"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")
        return result.stdout.strip()

    def generate(self, keyword_data: dict, date_str: str) -> str | None:
        os.makedirs(self.output_dir, exist_ok=True)
        prompt = self.assemble_prompt(keyword_data)

        max_attempts = 1 + self.claude_config["max_retries"]
        for attempt in range(max_attempts):
            try:
                draft = self.call_claude(prompt)
            except Exception as e:
                logger.error(f"Claude CLI error (attempt {attempt + 1}): {e}")
                continue

            if self.validate_draft(draft):
                slug = keyword_data["keyword"].lower().replace(" ", "-")
                filename = f"{date_str}-{slug}.md"
                output_path = os.path.join(self.output_dir, filename)
                with open(output_path, "w") as f:
                    f.write(draft)
                logger.info(f"Draft saved to {output_path}")
                return output_path

            logger.warning(f"Validation failed (attempt {attempt + 1}), retrying...")

        logger.error(f"Failed to generate valid draft for '{keyword_data['keyword']}'")
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/imchangi/SipeProjects/auto-blog && python -m pytest tests/test_content_generator.py -v`
Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add modules/content_generator.py tests/test_content_generator.py prompts/
git commit -m "feat: add content generator with Claude Code CLI integration and prompt templates"
```

---

## Task 4: Blogger Uploader

**Files:**
- Create: `modules/blogger_uploader.py`
- Create: `tests/test_blogger_uploader.py`
- Create: `setup_auth.py`

- [ ] **Step 1: Write failing tests**

`tests/test_blogger_uploader.py`:
```python
import json
import os
import pytest
from unittest.mock import patch, MagicMock
from modules.blogger_uploader import BloggerUploader


@pytest.fixture
def uploader(tmp_path):
    config = {
        "blogger": {
            "blog_id": "test-blog-123",
            "credentials_path": str(tmp_path / "oauth.json"),
            "token_path": str(tmp_path / "token.json"),
        },
    }
    return BloggerUploader(
        config=config,
        posted_keywords_path=str(tmp_path / "posted.json"),
    )


@pytest.fixture(autouse=True)
def setup_posted(tmp_path):
    with open(tmp_path / "posted.json", "w") as f:
        json.dump([], f)


class TestMarkdownToHtml:
    def test_converts_heading(self, uploader):
        html = uploader.markdown_to_html("## Hello World")
        assert "<h2>" in html
        assert "Hello World" in html

    def test_converts_paragraph(self, uploader):
        html = uploader.markdown_to_html("This is a paragraph.")
        assert "<p>" in html

    def test_converts_list(self, uploader):
        html = uploader.markdown_to_html("- item 1\n- item 2")
        assert "<li>" in html


class TestExtractMeta:
    def test_extracts_title_from_h1(self, uploader):
        draft = "# My Great Title\n\nSome content"
        meta = uploader.extract_meta(draft)
        assert meta["title"] == "My Great Title"

    def test_extracts_meta_description(self, uploader):
        draft = "META: This is a description\n\n# Title\n\nContent"
        meta = uploader.extract_meta(draft)
        assert meta["description"] == "This is a description"

    def test_strips_meta_from_content(self, uploader):
        draft = "META: Description\n\n# Title\n\nContent"
        meta = uploader.extract_meta(draft)
        assert "META:" not in meta["clean_content"]


class TestUpload:
    @patch("modules.blogger_uploader.BloggerUploader.get_service")
    def test_posts_to_blogger_api(self, mock_get_service, uploader, tmp_path):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_posts = mock_service.posts.return_value
        mock_posts.insert.return_value.execute.return_value = {
            "id": "post-456",
            "url": "https://myblog.blogspot.com/2026/03/test.html",
        }

        draft_path = tmp_path / "draft.md"
        draft_path.write_text("# Test Title\n\n## Section 1\n\nContent here.\n\n## Section 2\n\nMore.")

        keyword_data = {
            "keyword": "AI cooking",
            "category": "cooking",
        }

        result = uploader.upload(str(draft_path), keyword_data, ["AI", "cooking"])
        assert result["url"] == "https://myblog.blogspot.com/2026/03/test.html"
        mock_posts.insert.assert_called_once()

    @patch("modules.blogger_uploader.BloggerUploader.get_service")
    def test_records_posted_keyword(self, mock_get_service, uploader, tmp_path):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_posts = mock_service.posts.return_value
        mock_posts.insert.return_value.execute.return_value = {
            "id": "post-456",
            "url": "https://myblog.blogspot.com/2026/03/test.html",
        }

        draft_path = tmp_path / "draft.md"
        draft_path.write_text("# Title\n\n## S1\n\nText.\n\n## S2\n\nMore.")

        keyword_data = {"keyword": "AI cooking", "category": "cooking"}
        uploader.upload(str(draft_path), keyword_data, ["AI", "cooking"])

        with open(tmp_path / "posted.json") as f:
            posted = json.load(f)
        assert "AI cooking" in posted
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/imchangi/SipeProjects/auto-blog && python -m pytest tests/test_blogger_uploader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.blogger_uploader'`

- [ ] **Step 3: Implement blogger_uploader.py**

`modules/blogger_uploader.py`:
```python
import json
import os
import re
import logging

import markdown
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/blogger"]


class BloggerUploader:
    def __init__(self, config: dict, posted_keywords_path: str):
        self.config = config
        self.blogger_config = config["blogger"]
        self.posted_keywords_path = posted_keywords_path

    def markdown_to_html(self, md_text: str) -> str:
        return markdown.markdown(md_text, extensions=["extra", "codehilite"])

    def extract_meta(self, draft: str) -> dict:
        lines = draft.strip().split("\n")
        description = ""
        content_start = 0

        if lines[0].startswith("META:"):
            description = lines[0].replace("META:", "").strip()
            content_start = 1
            while content_start < len(lines) and lines[content_start].strip() == "":
                content_start += 1

        clean_content = "\n".join(lines[content_start:])

        title_match = re.search(r"^#\s+(.+)", clean_content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else "Untitled"

        return {
            "title": title,
            "description": description,
            "clean_content": clean_content,
        }

    def get_service(self):
        creds = None
        token_path = self.blogger_config["token_path"]
        credentials_path = self.blogger_config["credentials_path"]

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as token:
                token.write(creds.to_json())

        return build("blogger", "v3", credentials=creds)

    def upload(self, draft_path: str, keyword_data: dict, labels: list[str]) -> dict:
        with open(draft_path) as f:
            draft = f.read()

        meta = self.extract_meta(draft)
        html_content = self.markdown_to_html(meta["clean_content"])

        service = self.get_service()
        blog_id = self.blogger_config["blog_id"]

        body = {
            "kind": "blogger#post",
            "title": meta["title"],
            "content": html_content,
            "labels": labels,
        }

        result = service.posts().insert(blogId=blog_id, body=body).execute()

        self._record_posted(keyword_data["keyword"])

        logger.info(f"Published: {result.get('url', 'unknown URL')}")
        return result

    def _record_posted(self, keyword: str):
        with open(self.posted_keywords_path) as f:
            posted = json.load(f)
        posted.append(keyword)
        with open(self.posted_keywords_path, "w") as f:
            json.dump(posted, f, indent=2)
```

- [ ] **Step 4: Implement setup_auth.py**

`setup_auth.py`:
```python
"""One-time setup script for Blogger API OAuth authentication.

Usage:
    1. Place your Google OAuth client JSON at credentials/google_oauth.json
    2. Run: python setup_auth.py
    3. A browser window will open for Google login
    4. After login, the token is saved to credentials/token.json
"""

import os
import yaml
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/blogger"]


def main():
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    credentials_path = config["blogger"]["credentials_path"]
    token_path = config["blogger"]["token_path"]

    if not os.path.exists(credentials_path):
        print(f"ERROR: OAuth client file not found at {credentials_path}")
        print("Download it from Google Cloud Console > APIs & Services > Credentials")
        return

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            print("Token refreshed.")
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
            print("Authentication successful.")

        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
        print(f"Token saved to {token_path}")
    else:
        print("Token is already valid.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/imchangi/SipeProjects/auto-blog && python -m pytest tests/test_blogger_uploader.py -v`
Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add modules/blogger_uploader.py tests/test_blogger_uploader.py setup_auth.py
git commit -m "feat: add Blogger uploader with OAuth and setup script"
```

---

## Task 5: Orchestrator

**Files:**
- Create: `orchestrator.py`
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests**

`tests/test_orchestrator.py`:
```python
import json
import os
import pytest
from unittest.mock import patch, MagicMock
from orchestrator import Orchestrator


@pytest.fixture
def orch(tmp_path):
    config = {
        "blogger": {
            "blog_id": "test-blog",
            "credentials_path": str(tmp_path / "oauth.json"),
            "token_path": str(tmp_path / "token.json"),
        },
        "schedule": {
            "posts_per_week": [3, 4],
            "time_range_hours": [6, 22],
            "random_delay_max_hours": 0,
        },
        "content": {
            "language": "en",
            "min_word_count": 800,
            "target_audience": "non-tech adults",
            "tone": "friendly",
            "categories": ["cooking", "travel"],
        },
        "trends": {
            "region": "US",
            "lookback_days": 7,
            "max_keywords_per_run": 3,
        },
        "claude": {
            "timeout_seconds": 120,
            "max_retries": 1,
        },
    }
    return Orchestrator(config=config, base_dir=str(tmp_path))


class TestShouldPostToday:
    def test_returns_bool(self, orch):
        result = orch.should_post_today()
        assert isinstance(result, bool)

    @patch("orchestrator.Orchestrator.posts_this_week", return_value=4)
    def test_no_post_when_max_reached(self, mock_posts, orch):
        assert orch.should_post_today() is False

    @patch("orchestrator.Orchestrator.posts_this_week", return_value=0)
    @patch("orchestrator.random.random", return_value=0.1)
    def test_posts_when_probability_met(self, mock_rand, mock_posts, orch):
        assert orch.should_post_today() is True


class TestPostsThisWeek:
    def test_counts_from_posted_log(self, orch, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        # No posts yet
        assert orch.posts_this_week() == 0


class TestRunPipeline:
    @patch("orchestrator.BloggerUploader")
    @patch("orchestrator.ContentGenerator")
    @patch("orchestrator.TrendResearcher")
    def test_full_pipeline(self, MockResearcher, MockGenerator, MockUploader, orch, tmp_path):
        # Setup mocks
        mock_researcher = MockResearcher.return_value
        keywords_path = str(tmp_path / "keywords" / "2026-03-30.json")
        os.makedirs(tmp_path / "keywords", exist_ok=True)
        with open(keywords_path, "w") as f:
            json.dump([{
                "keyword": "AI cooking",
                "category": "cooking",
                "template": "howto_apply",
                "title_suggestion": "How to Use AI for Cooking",
                "related_queries": ["ChatGPT recipes"],
                "score": 0.5,
            }], f)
        mock_researcher.run.return_value = keywords_path

        mock_generator = MockGenerator.return_value
        draft_path = str(tmp_path / "drafts" / "2026-03-30-ai-cooking.md")
        os.makedirs(tmp_path / "drafts", exist_ok=True)
        with open(draft_path, "w") as f:
            f.write("# Test\n\nContent")
        mock_generator.generate.return_value = draft_path

        mock_uploader = MockUploader.return_value
        mock_uploader.upload.return_value = {"url": "https://blog.com/post"}

        result = orch.run_pipeline()
        assert result is True
        mock_researcher.run.assert_called_once()
        mock_generator.generate.assert_called_once()
        mock_uploader.upload.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/imchangi/SipeProjects/auto-blog && python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'orchestrator'`

- [ ] **Step 3: Implement orchestrator.py**

`orchestrator.py`:
```python
import json
import os
import random
import logging
import time
from datetime import datetime

import yaml

from modules.trend_researcher import TrendResearcher
from modules.content_generator import ContentGenerator
from modules.blogger_uploader import BloggerUploader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join("logs", f"{datetime.now().strftime('%Y-%m-%d')}.log")
        ),
    ],
)
logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, config: dict, base_dir: str = "."):
        self.config = config
        self.base_dir = base_dir
        self.schedule = config["schedule"]

    def posts_this_week(self) -> int:
        log_dir = os.path.join(self.base_dir, "logs")
        if not os.path.exists(log_dir):
            return 0

        today = datetime.now()
        weekday = today.weekday()
        count = 0

        posted_path = os.path.join(self.base_dir, "data", "posted_keywords.json")
        if not os.path.exists(posted_path):
            return 0

        # Count log files from this week (Mon-Sun)
        for f in os.listdir(log_dir):
            if f.endswith(".log"):
                try:
                    log_date = datetime.strptime(f.replace(".log", ""), "%Y-%m-%d")
                    days_diff = (today - log_date).days
                    if days_diff <= weekday:
                        log_path = os.path.join(log_dir, f)
                        with open(log_path) as lf:
                            if "Published:" in lf.read():
                                count += 1
                except ValueError:
                    continue
        return count

    def should_post_today(self) -> bool:
        current_count = self.posts_this_week()
        max_posts = self.schedule["posts_per_week"][1]

        if current_count >= max_posts:
            logger.info(f"Already posted {current_count} times this week (max {max_posts}). Skipping.")
            return False

        today = datetime.now()
        weekday = today.weekday()
        remaining_days = 7 - weekday
        min_posts = self.schedule["posts_per_week"][0]
        needed = max(0, min_posts - current_count)

        if remaining_days <= 0:
            return False

        probability = max(needed / remaining_days, 0.5)
        probability = min(probability, 1.0)

        roll = random.random()
        should_post = roll < probability
        logger.info(f"Post decision: count={current_count}, needed={needed}, remaining_days={remaining_days}, prob={probability:.2f}, roll={roll:.2f}, post={should_post}")
        return should_post

    def run_pipeline(self) -> bool:
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Step 1: Trend Research
        logger.info("=== Step 1: Trend Research ===")
        researcher = TrendResearcher(
            config=self.config,
            output_dir=os.path.join(self.base_dir, "output", "keywords"),
            posted_keywords_path=os.path.join(self.base_dir, "data", "posted_keywords.json"),
        )
        keywords_path = researcher.run()

        with open(keywords_path) as f:
            keywords = json.load(f)

        if not keywords:
            logger.warning("No keywords found. Skipping.")
            return False

        keyword_data = keywords[0]
        logger.info(f"Selected keyword: {keyword_data['keyword']}")

        # Step 2: Content Generation
        logger.info("=== Step 2: Content Generation ===")
        generator = ContentGenerator(
            config=self.config,
            prompts_dir=os.path.join(self.base_dir, "prompts"),
            output_dir=os.path.join(self.base_dir, "output", "drafts"),
        )
        draft_path = generator.generate(keyword_data, date_str)

        if draft_path is None:
            logger.error("Content generation failed. Skipping upload.")
            return False

        # Step 3: Upload
        logger.info("=== Step 3: Blogger Upload ===")
        uploader = BloggerUploader(
            config=self.config,
            posted_keywords_path=os.path.join(self.base_dir, "data", "posted_keywords.json"),
        )
        labels = ["AI", keyword_data["category"]] + keyword_data["keyword"].split()
        labels = list(set(labels))
        result = uploader.upload(draft_path, keyword_data, labels)

        logger.info(f"Published: {result.get('url', 'unknown')}")
        return True

    def run(self):
        logger.info("=== Auto Blog Orchestrator Started ===")

        # Random delay for natural timing
        delay_max = self.schedule.get("random_delay_max_hours", 0)
        if delay_max > 0:
            delay_seconds = random.uniform(0, delay_max * 3600)
            logger.info(f"Random delay: {delay_seconds / 60:.1f} minutes")
            time.sleep(delay_seconds)

        if not self.should_post_today():
            logger.info("Decided not to post today. Exiting.")
            return

        try:
            self.run_pipeline()
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)

        logger.info("=== Orchestrator Finished ===")


def main():
    os.makedirs("logs", exist_ok=True)

    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    orch = Orchestrator(config=config, base_dir=".")
    orch.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/imchangi/SipeProjects/auto-blog && python -m pytest tests/test_orchestrator.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add orchestrator with random scheduling and pipeline execution"
```

---

## Task 6: Integration Test & Cron Setup

**Files:**
- Create: `tests/test_integration.py`
- Modify: no files modified, cron setup is manual instruction

- [ ] **Step 1: Write integration test (mocked external services)**

`tests/test_integration.py`:
```python
"""Integration test: runs the full pipeline with mocked external services."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

import pandas as pd

from orchestrator import Orchestrator


@pytest.fixture
def full_setup(tmp_path):
    # Config
    config = {
        "blogger": {
            "blog_id": "test-blog",
            "credentials_path": str(tmp_path / "oauth.json"),
            "token_path": str(tmp_path / "token.json"),
        },
        "schedule": {
            "posts_per_week": [3, 4],
            "time_range_hours": [6, 22],
            "random_delay_max_hours": 0,
        },
        "content": {
            "language": "en",
            "min_word_count": 50,  # lowered for test
            "target_audience": "non-tech adults",
            "tone": "friendly",
            "categories": ["cooking"],
        },
        "trends": {
            "region": "US",
            "lookback_days": 7,
            "max_keywords_per_run": 1,
        },
        "claude": {
            "timeout_seconds": 30,
            "max_retries": 0,
        },
    }

    # Create directories
    for d in ["output/keywords", "output/drafts", "data", "logs", "prompts"]:
        os.makedirs(tmp_path / d, exist_ok=True)

    # Prompt template
    (tmp_path / "prompts" / "daily_ai_tips.md").write_text(
        "Write about {{keyword}}. Title: {{title}}. Related: {{related_queries}}"
    )

    # Empty posted keywords
    with open(tmp_path / "data" / "posted_keywords.json", "w") as f:
        json.dump([], f)

    return config, tmp_path


@patch("modules.blogger_uploader.BloggerUploader.get_service")
@patch("modules.content_generator.subprocess.run")
@patch("modules.trend_researcher.TrendReq")
def test_full_pipeline_end_to_end(mock_trendreq_cls, mock_subprocess, mock_get_service, full_setup):
    config, tmp_path = full_setup

    # Mock pytrends
    mock_pytrends = MagicMock()
    mock_trendreq_cls.return_value = mock_pytrends
    mock_pytrends.interest_over_time.return_value = pd.DataFrame(
        {"AI cooking": [50, 60, 80]}
    )
    mock_pytrends.related_queries.return_value = {
        "AI cooking": {
            "top": pd.DataFrame({"query": ["ChatGPT recipes", "AI meal planner"]}),
        }
    }

    # Mock Claude CLI
    fake_article = (
        "# How to Use AI for Cooking\n\n"
        "## Introduction\n\n" + "word " * 60 + "\n\n"
        "## Step by Step\n\nMore content here.\n\n"
        "## Conclusion\n\nFinal thoughts."
    )
    mock_subprocess.return_value = MagicMock(returncode=0, stdout=fake_article)

    # Mock Blogger API
    mock_service = MagicMock()
    mock_get_service.return_value = mock_service
    mock_posts = mock_service.posts.return_value
    mock_posts.insert.return_value.execute.return_value = {
        "id": "post-789",
        "url": "https://myblog.blogspot.com/2026/03/ai-cooking.html",
    }

    # Run
    orch = Orchestrator(config=config, base_dir=str(tmp_path))
    result = orch.run_pipeline()

    assert result is True

    # Verify keyword file was created
    keyword_files = os.listdir(tmp_path / "output" / "keywords")
    assert len(keyword_files) == 1

    # Verify draft was created
    draft_files = os.listdir(tmp_path / "output" / "drafts")
    assert len(draft_files) == 1

    # Verify keyword was recorded as posted
    with open(tmp_path / "data" / "posted_keywords.json") as f:
        posted = json.load(f)
    assert "AI cooking" in posted

    # Verify Blogger API was called
    mock_posts.insert.assert_called_once()
```

- [ ] **Step 2: Run all tests**

Run: `cd /Users/imchangi/SipeProjects/auto-blog && python -m pytest tests/ -v`
Expected: All tests PASS (unit + integration)

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration test for full pipeline"
```

- [ ] **Step 4: Document cron setup in config.example.yaml**

Add this comment block at the top of `config.example.yaml`:
```yaml
# ============================================
# Auto Blog Generator Configuration
# ============================================
# Setup:
#   1. Copy this file to config.yaml: cp config.example.yaml config.yaml
#   2. Fill in your blog_id
#   3. Run: python setup_auth.py
#   4. Cron setup:
#      crontab -e
#      0 10 * * * cd /path/to/auto-blog && /path/to/python orchestrator.py >> logs/cron.log 2>&1
# ============================================
```

- [ ] **Step 5: Final commit**

```bash
git add config.example.yaml
git commit -m "docs: add setup instructions to config template"
```

---

## Summary

| Task | Module | Tests |
|------|--------|-------|
| 1 | Project scaffolding | — |
| 2 | Trend Researcher | 8 tests |
| 3 | Content Generator + Prompts | 7 tests |
| 4 | Blogger Uploader + Auth Setup | 7 tests |
| 5 | Orchestrator | 5 tests |
| 6 | Integration Test + Cron | 1 test |

**Total: 28 tests**
