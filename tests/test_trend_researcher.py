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
