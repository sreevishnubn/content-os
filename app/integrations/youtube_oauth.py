"""Local/server-side OAuth helper for YouTube."""

import json
import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def load_credentials(token_path: str = "data/youtube_token.json") -> Credentials | None:
    path = Path(token_path)
    if not path.exists():
        return None
    return Credentials.from_authorized_user_file(path, SCOPES)


def run_local_oauth(
    client_secret_path: str,
    token_path: str = "data/youtube_token.json",
) -> Credentials:
    """Run one interactive OAuth consent flow locally, then store the token securely."""
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
    credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    path = Path(token_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(credentials.to_json(), encoding="utf-8")
    os.chmod(path, 0o600)
    return credentials
