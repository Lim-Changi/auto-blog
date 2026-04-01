import pytest
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
