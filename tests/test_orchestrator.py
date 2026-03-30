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
        assert orch.posts_this_week() == 0


class TestRunPipeline:
    @patch("orchestrator.BloggerUploader")
    @patch("orchestrator.ContentGenerator")
    @patch("orchestrator.TrendResearcher")
    def test_full_pipeline(self, MockResearcher, MockGenerator, MockUploader, orch, tmp_path):
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
