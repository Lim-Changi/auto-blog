import json
import os
import re
import logging

import markdown
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/blogger"]


class BloggerUploader:
    def __init__(self, config: dict, posted_keywords_path: str):
        self.config = config
        self.blogger_config = config["blogger"]
        self.posted_keywords_path = posted_keywords_path

    def markdown_to_html(self, md_text: str) -> str:
        return markdown.markdown(md_text, extensions=["extra", "codehilite"])

    def extract_meta(self, draft: str) -> dict:
        lines = draft.strip().split("\n")
        description = ""
        content_start = 0

        if lines[0].startswith("META:"):
            description = lines[0].replace("META:", "").strip()
            content_start = 1
            while content_start < len(lines) and lines[content_start].strip() == "":
                content_start += 1

        clean_content = "\n".join(lines[content_start:])

        title_match = re.search(r"^#\s+(.+)", clean_content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else "Untitled"

        return {
            "title": title,
            "description": description,
            "clean_content": clean_content,
        }

    def get_service(self):
        creds = None
        token_path = self.blogger_config["token_path"]
        credentials_path = self.blogger_config["credentials_path"]

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as token:
                token.write(creds.to_json())

        return build("blogger", "v3", credentials=creds)

    def upload(self, draft_path: str, keyword_data: dict, labels: list[str]) -> dict:
        with open(draft_path) as f:
            draft = f.read()

        meta = self.extract_meta(draft)
        html_content = self.markdown_to_html(meta["clean_content"])

        service = self.get_service()
        blog_id = self.blogger_config["blog_id"]

        body = {
            "kind": "blogger#post",
            "title": meta["title"],
            "content": html_content,
            "labels": labels,
        }

        result = service.posts().insert(blogId=blog_id, body=body).execute()

        self._record_posted(keyword_data["keyword"])

        logger.info(f"Published: {result.get('url', 'unknown URL')}")
        return result

    def _record_posted(self, keyword: str):
        if os.path.exists(self.posted_keywords_path):
            with open(self.posted_keywords_path) as f:
                posted = json.load(f)
        else:
            posted = []
        posted.append(keyword)
        with open(self.posted_keywords_path, "w") as f:
            json.dump(posted, f, indent=2)
