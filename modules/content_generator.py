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

    def clean_draft(self, raw: str) -> str:
        """Extract only the blog article from Claude's output.

        Claude sometimes prepends/appends conversational text like
        'Here is the article:' or 'I hope this helps!'. This method
        extracts content starting from the META: line or first heading.
        """
        lines = raw.split("\n")

        # Find start: META: line or first heading
        start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("META:") or re.match(r"^#{1,2}\s+", line):
                start = i
                break

        # Find end: trim trailing non-content lines
        end = len(lines)
        for i in range(len(lines) - 1, start, -1):
            stripped = lines[i].strip()
            if stripped == "" or stripped == "---":
                end = i
                continue
            # Stop trimming if we hit actual content
            if re.match(r"^#{1,3}\s+", stripped) or len(stripped) > 20:
                end = i + 1
                break

        cleaned = "\n".join(lines[start:end]).strip()
        if cleaned != raw.strip():
            logger.info("Cleaned non-article content from Claude output")
        return cleaned

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
        logger.debug(f"Prompt length: {len(prompt)} chars")
        result = subprocess.run(
            ["claude", "-p", "-", "--output-format", "text"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        logger.debug(f"Claude stdout ({len(result.stdout)} chars): {result.stdout[:200]!r}")
        logger.debug(f"Claude stderr: {result.stderr[:500]!r}")
        logger.debug(f"Claude returncode: {result.returncode}")
        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")
        return result.stdout.strip()

    def generate(self, keyword_data: dict, date_str: str) -> str | None:
        os.makedirs(self.output_dir, exist_ok=True)
        prompt = self.assemble_prompt(keyword_data)

        max_attempts = 1 + self.claude_config["max_retries"]
        for attempt in range(max_attempts):
            try:
                raw = self.call_claude(prompt)
                draft = self.clean_draft(raw)
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
