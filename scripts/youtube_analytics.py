"""Pull a channel-level YouTube Analytics report."""

import argparse
import json

from app.integrations.youtube import YouTubeProvider
from app.integrations.youtube_oauth import load_credentials


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("start_date")
    parser.add_argument("end_date")
    parser.add_argument("--token", default="data/youtube_token.json")
    args = parser.parse_args()

    credentials = load_credentials(args.token)
    if credentials is None or not credentials.valid:
        raise RuntimeError("Valid YouTube OAuth credentials are required")

    report = YouTubeProvider(credentials).channel_report(args.start_date, args.end_date)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
