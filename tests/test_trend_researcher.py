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
        "claude": {
            "timeout_seconds": 120,
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


class TestBuildResearchPrompt:
    def test_includes_categories(self, researcher):
        prompt = researcher._build_research_prompt()
        assert "cooking" in prompt
        assert "travel" in prompt
        assert "fitness" in prompt

    def test_includes_posted_keywords(self, researcher, tmp_path):
        with open(tmp_path / "posted.json", "w") as f:
            json.dump(["AI cooking tips"], f)
        prompt = researcher._build_research_prompt()
        assert "AI cooking tips" in prompt

    def test_includes_max_keywords(self, researcher):
        prompt = researcher._build_research_prompt()
        assert "3" in prompt


class TestParseKeywords:
    def test_parses_clean_json(self, researcher):
        raw = '[{"keyword": "AI meal planning", "category": "cooking"}]'
        result = researcher._parse_keywords(raw)
        assert len(result) == 1
        assert result[0]["keyword"] == "AI meal planning"

    def test_parses_json_in_code_fence(self, researcher):
        raw = '```json\n[{"keyword": "AI meal planning"}]\n```'
        result = researcher._parse_keywords(raw)
        assert len(result) == 1

    def test_parses_json_with_preamble(self, researcher):
        raw = 'Here are the results:\n[{"keyword": "AI meal planning"}]'
        result = researcher._parse_keywords(raw)
        assert len(result) == 1

    def test_returns_empty_on_garbage(self, researcher):
        result = researcher._parse_keywords("not valid json at all")
        assert result == []


class TestNormalizeKeywords:
    def test_maps_content_angle_to_template(self, researcher):
        keywords = [
            {"keyword": "AI cooking guide", "content_angle": "howto", "interest": 80},
            {"keyword": "best AI travel apps", "content_angle": "tools", "interest": 70},
            {"keyword": "AI fitness tips", "content_angle": "tips", "interest": 60},
        ]
        result = researcher._normalize_keywords(keywords)
        templates = {r["keyword"]: r["template"] for r in result}
        assert templates["AI cooking guide"] == "howto_apply"
        assert templates["best AI travel apps"] == "best_tools"
        assert templates["AI fitness tips"] == "daily_ai_tips"

    def test_filters_posted_keywords(self, researcher, tmp_path):
        with open(tmp_path / "posted.json", "w") as f:
            json.dump(["AI cooking guide"], f)
        keywords = [
            {"keyword": "AI cooking guide", "interest": 80},
            {"keyword": "AI travel planner", "interest": 70},
        ]
        result = researcher._normalize_keywords(keywords)
        assert len(result) == 1
        assert result[0]["keyword"] == "AI travel planner"

    def test_scores_by_demand_and_competition(self, researcher):
        keywords = [
            {"keyword": "low score", "interest": 50, "search_demand": "low", "competition": "high"},
            {"keyword": "high score", "interest": 90, "search_demand": "high", "competition": "low"},
        ]
        result = researcher._normalize_keywords(keywords)
        assert result[0]["keyword"] == "high score"
        assert result[0]["score"] > result[1]["score"]

    def test_skips_empty_keywords(self, researcher):
        keywords = [{"keyword": "", "interest": 80}, {"keyword": "valid", "interest": 70}]
        result = researcher._normalize_keywords(keywords)
        assert len(result) == 1


class TestEnrichKeywords:
    def test_adds_title_for_howto(self, researcher):
        keywords = [{"keyword": "AI meal planning", "template": "howto_apply"}]
        result = researcher._enrich_keywords(keywords)
        assert "How to Use AI" in result[0]["title_suggestion"]

    def test_adds_title_for_tools(self, researcher):
        keywords = [{"keyword": "AI travel apps", "template": "best_tools"}]
        result = researcher._enrich_keywords(keywords)
        assert "Best Free AI Tools" in result[0]["title_suggestion"]

    def test_adds_title_for_tips(self, researcher):
        keywords = [{"keyword": "AI cooking", "template": "daily_ai_tips"}]
        result = researcher._enrich_keywords(keywords)
        assert "5 Easy Ways" in result[0]["title_suggestion"]


class TestRun:
    @patch.object(TrendResearcher, "_call_claude")
    def test_run_saves_json(self, mock_claude, researcher, tmp_path):
        mock_claude.return_value = json.dumps([
            {
                "keyword": "AI meal planning",
                "category": "cooking",
                "interest": 82,
                "search_demand": "high",
                "competition": "low",
                "related_queries": ["ChatGPT meal prep"],
                "content_angle": "howto",
                "reasoning": "trending topic",
            },
        ])
        result_path = researcher.run()
        assert os.path.exists(result_path)
        with open(result_path) as f:
            data = json.load(f)
        assert len(data) >= 1
        assert data[0]["keyword"] == "AI meal planning"
        assert "template" in data[0]
        assert "title_suggestion" in data[0]
        assert "score" in data[0]

    @patch.object(TrendResearcher, "_call_claude")
    def test_falls_back_to_cache_on_failure(self, mock_claude, researcher, tmp_path):
        os.makedirs(tmp_path / "keywords", exist_ok=True)
        with open(tmp_path / "keywords" / "2026-03-29.json", "w") as f:
            json.dump([{
                "keyword": "AI grocery shopping",
                "category": "shopping",
                "interest": 70,
                "template": "daily_ai_tips",
                "title_suggestion": "5 Easy Ways...",
                "score": 5.0,
                "related_queries": [],
            }], f)

        mock_claude.side_effect = RuntimeError("timeout")
        result_path = researcher.run()
        with open(result_path) as f:
            data = json.load(f)
        assert len(data) >= 1
        assert data[0]["keyword"] == "AI grocery shopping"
