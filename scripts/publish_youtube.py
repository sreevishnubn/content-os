"""Publish one rendered video to YouTube using an existing OAuth token.

Use this only after human review has marked the content approved/ready.
"""

import argparse
import json

from app.integrations.youtube import YouTubeProvider
from app.integrations.youtube_oauth import load_credentials


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--tags", default="")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    parser.add_argument("--token", default="data/youtube_token.json")
    args = parser.parse_args()

    credentials = load_credentials(args.token)
    if credentials is None or not credentials.valid:
        raise RuntimeError("Valid YouTube OAuth credentials are required")

    result = YouTubeProvider(credentials).upload_video(
        args.video,
        title=args.title,
        description=args.description,
        tags=[tag.strip() for tag in args.tags.split(",") if tag.strip()],
        privacy_status=args.privacy,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
