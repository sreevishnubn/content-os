"""YouTube publishing and analytics adapter.

OAuth credentials are read from environment/configured secret storage. No
refresh token is ever sent to the browser.
"""

from pathlib import Path
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class YouTubeProvider:
    name = "youtube"

    def __init__(self, credentials: Any) -> None:
        self.youtube = build("youtube", "v3", credentials=credentials)
        self.analytics = build("youtubeAnalytics", "v2", credentials=credentials)

    def upload_video(
        self,
        video_path: str,
        *,
        title: str,
        description: str,
        tags: list[str],
        privacy_status: str = "private",
        category_id: str = "22",
    ) -> dict[str, Any]:
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {"privacyStatus": privacy_status},
        }
        media = MediaFileUpload(Path(video_path).as_posix(), chunksize=-1, resumable=True)
        request = self.youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _, response = request.next_chunk()
        return response

    def channel_report(self, start_date: str, end_date: str) -> dict[str, Any]:
        response = self.analytics.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views,estimatedMinutesWatched,averageViewDuration,likes,comments,subscribersGained,impressions,impressionsClickThroughRate",
            dimensions="day",
            sort="day",
        ).execute()
        return response
