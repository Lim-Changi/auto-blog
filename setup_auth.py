"""One-time setup script for Blogger API OAuth authentication.

Usage:
    1. Place your Google OAuth client JSON at credentials/google_oauth.json
    2. Run: python setup_auth.py
    3. A browser window will open for Google login
    4. After login, the token is saved to credentials/token.json
"""

import os
import yaml
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/blogger"]


def main():
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    credentials_path = config["blogger"]["credentials_path"]
    token_path = config["blogger"]["token_path"]

    if not os.path.exists(credentials_path):
        print(f"ERROR: OAuth client file not found at {credentials_path}")
        print("Download it from Google Cloud Console > APIs & Services > Credentials")
        return

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            print("Token refreshed.")
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
            print("Authentication successful.")

        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
        print(f"Token saved to {token_path}")
    else:
        print("Token is already valid.")


if __name__ == "__main__":
    main()
