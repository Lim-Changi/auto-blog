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
