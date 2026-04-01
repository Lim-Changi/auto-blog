import pytest
from unittest.mock import patch
from modules.content_validator import ContentValidator


@pytest.fixture
def validator():
    config = {
        "claude": {"path": "claude", "timeout_seconds": 120},
        "validator": {"max_fix_attempts": 2, "enabled": True},
    }
    return ContentValidator(config=config, prompts_dir="prompts")


class TestCheckAiPatterns:
    def test_detects_banned_phrases(self, validator):
        text = "In today's rapidly evolving world, AI is changing everything."
        issues = validator._check_ai_patterns(text)
        assert any("banned phrase" in i.lower() for i in issues)

    def test_detects_multiple_banned_phrases(self, validator):
        text = (
            "It's worth noting that AI is powerful. "
            "Furthermore, let's dive in to the details."
        )
        issues = validator._check_ai_patterns(text)
        banned_issues = [i for i in issues if "banned phrase" in i.lower()]
        assert len(banned_issues) >= 2

    def test_detects_uniform_paragraphs(self, validator):
        # All paragraphs have ~20 words — too uniform
        para = "This is a paragraph with exactly twenty words in it to test the uniformity detection logic here now. "
        text = (para + "\n\n") * 5
        issues = validator._check_ai_patterns(text)
        assert any("uniform" in i.lower() for i in issues)

    def test_allows_varied_paragraphs(self, validator):
        text = (
            "Short one.\n\n"
            "This is a medium length paragraph with a few more words in it for variety.\n\n"
            "And here is a much longer paragraph that goes on for quite a while to really "
            "make sure the standard deviation is high enough to pass the uniformity check "
            "and not trigger any false positives in our detection logic."
        )
        issues = validator._check_ai_patterns(text)
        assert not any("uniform" in i.lower() for i in issues)

    def test_allows_varied_paragraphs_above_threshold(self, validator):
        # 4+ paragraphs with genuinely varied lengths (CV > 0.2)
        text = (
            "Short thought here.\n\n"
            "This one is a bit longer with more words to fill it out nicely.\n\n"
            "Here is a much longer paragraph that really goes into detail about the topic at hand "
            "and provides a lot of extra context and information to make sure the word count "
            "is significantly different from the short paragraph above.\n\n"
            "Medium length works too."
        )
        issues = validator._check_ai_patterns(text)
        assert not any("uniform" in i.lower() for i in issues)

    def test_detects_repetitive_openers(self, validator):
        text = (
            "This is the first sentence. This is the second. "
            "This is the third. This is the fourth."
        )
        issues = validator._check_ai_patterns(text)
        assert any("repetitive" in i.lower() for i in issues)

    def test_clean_text_returns_empty(self, validator):
        text = (
            "I tried using ChatGPT for meal planning last week.\n\n"
            "Honestly, it was a game changer. The suggestions were spot on.\n\n"
            "My family loved the variety. Even my picky kid ate everything."
        )
        issues = validator._check_ai_patterns(text)
        assert issues == []


class TestValidateAndFix:
    def test_clean_draft_passes_without_claude_call(self, validator, tmp_path):
        draft = (
            "META: A guide to meal planning with AI.\n\n"
            "# How to Use AI for Meal Planning\n\n"
            "I tried using ChatGPT for meal planning last week.\n\n"
            "Honestly, it was a game changer for me personally. "
            "The suggestions were spot on and my family loved them.\n\n"
            "My family loved the variety. Even my picky kid ate everything. "
            "We saved about $50 on groceries that week.\n\n"
            "Here's exactly what I did step by step to get started.\n\n"
            "First, I opened up ChatGPT and typed in a simple prompt."
        )
        draft_path = tmp_path / "draft.md"
        draft_path.write_text(draft)

        with patch.object(validator, "_call_claude") as mock_claude:
            result = validator.validate_and_fix(str(draft_path))
            mock_claude.assert_not_called()
            assert result == str(draft_path)

    def test_calls_claude_when_issues_found(self, validator, tmp_path):
        draft = (
            "META: A guide.\n\n"
            "# Title\n\n"
            "In today's rapidly evolving world, AI is here.\n\n"
            "Furthermore, it's worth noting the changes.\n\n"
            "Let's dive in to the details of this topic.\n\n"
            "We will explore everything you need to know.\n\n"
            "This is a fairly long paragraph to make the word count work."
        )
        draft_path = tmp_path / "draft.md"
        draft_path.write_text(draft)

        fixed_content = (
            "META: A guide.\n\n"
            "# Title\n\n"
            "I started using AI tools about a month ago.\n\n"
            "What surprised me most was how simple it was.\n\n"
            "Here's what changed in my daily routine.\n\n"
            "The biggest difference? I actually had free time.\n\n"
            "My mornings went from chaotic to pretty calm."
        )

        with patch.object(validator, "_call_claude", return_value=fixed_content):
            result = validator.validate_and_fix(str(draft_path))
            assert result == str(draft_path)
            assert draft_path.read_text() == fixed_content

    def test_returns_none_after_max_attempts(self, validator, tmp_path):
        bad_draft = (
            "META: A guide.\n\n"
            "# Title\n\n"
            "In today's rapidly evolving world, AI is here.\n\n"
            "Furthermore, let's dive in.\n\n"
            "It's worth noting all the changes happening.\n\n"
            "The possibilities are endless for everyone."
        )
        draft_path = tmp_path / "draft.md"
        draft_path.write_text(bad_draft)

        # Claude keeps returning content with banned phrases
        with patch.object(validator, "_call_claude", return_value=bad_draft):
            result = validator.validate_and_fix(str(draft_path))
            assert result is None

    def test_disabled_validator_passes_through(self, tmp_path):
        config = {
            "claude": {"path": "claude", "timeout_seconds": 120},
            "validator": {"max_fix_attempts": 2, "enabled": False},
        }
        validator = ContentValidator(config=config, prompts_dir="prompts")
        draft_path = tmp_path / "draft.md"
        draft_path.write_text("In today's world, AI is great.")

        result = validator.validate_and_fix(str(draft_path))
        assert result == str(draft_path)
