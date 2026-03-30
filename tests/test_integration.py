"""Integration test: runs the full pipeline with mocked external services."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

import pandas as pd

from orchestrator import Orchestrator


@pytest.fixture
def full_setup(tmp_path):
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
            "min_word_count": 50,
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

    for d in ["output/keywords", "output/drafts", "data", "logs", "prompts"]:
        os.makedirs(tmp_path / d, exist_ok=True)

    (tmp_path / "prompts" / "daily_ai_tips.md").write_text(
        "Write about {{keyword}}. Title: {{title}}. Related: {{related_queries}}"
    )
    (tmp_path / "prompts" / "howto_apply.md").write_text(
        "Write about {{keyword}}. Title: {{title}}. Related: {{related_queries}}"
    )
    (tmp_path / "prompts" / "best_tools.md").write_text(
        "Write about {{keyword}}. Title: {{title}}. Related: {{related_queries}}"
    )

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
