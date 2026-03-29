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
