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
            "posts_per_day": 1,
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
    def test_returns_true_when_no_posts_today(self, orch, tmp_path):
        os.makedirs(tmp_path / "logs", exist_ok=True)
        assert orch.should_post_today() is True

    def test_returns_false_when_already_posted(self, orch, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir(exist_ok=True)
        from datetime import datetime
        log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        log_file.write_text("Published: https://blog.com/post")
        assert orch.should_post_today() is False


class TestPostsToday:
    def test_zero_when_no_log(self, orch):
        assert orch.posts_today() == 0

    def test_counts_published_entries(self, orch, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir(exist_ok=True)
        from datetime import datetime
        log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        log_file.write_text("Published: url1\nPublished: url2")
        assert orch.posts_today() == 2


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
