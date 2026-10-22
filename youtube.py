
import os
import requests
from html import unescape
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


def fetch_youtube_data(
    brand,
    max_videos=5,
    comments_per_video=20
):
    if not API_KEY:
        raise ValueError("YOUTUBE_API_KEY is missing")

    if not 1 <= max_videos <= 50:
        raise ValueError("max_videos must be between 1 and 50")

    if not 1 <= comments_per_video <= 100:
        raise ValueError("comments_per_video must be between 1 and 100")

    # 1. Search videos
    response = requests.get(
        SEARCH_URL,
        params={
            "key": API_KEY,
            "part": "snippet",
            "q": brand,
            "type": "video",
            "maxResults": max_videos
        },
        timeout=30
    )
    response.raise_for_status()

    search_results = response.json().get("items", [])

    videos = []
    comments = []

    for item in search_results:
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]

        # 2. Collect video metadata
        videos.append({
            "video_id": video_id,
            "title": unescape(snippet["title"]),
            "description": snippet.get("description"),
            "channel_title": snippet.get("channelTitle"),
            "published_at": snippet.get("publishedAt"),
            "url": f"https://www.youtube.com/watch?v={video_id}"
        })

        # 3. Fetch video comments
        response = requests.get(
            COMMENTS_URL,
            params={
                "key": API_KEY,
                "part": "snippet",
                "videoId": video_id,
                "maxResults": comments_per_video,
                "textFormat": "plainText"
            },
            timeout=30
        )

        if response.status_code == 403:
            errors = response.json().get(
                "error", {}
            ).get("errors", [])

            if any(
                e.get("reason") == "commentsDisabled"
                for e in errors
            ):
                continue

        response.raise_for_status()

        for thread in response.json().get("items", []):
            top_comment = thread["snippet"]["topLevelComment"]
            comment = top_comment["snippet"]
            comment_id = top_comment["id"]

            comments.append({
                "comment_id": comment_id,
                "video_id": video_id,
                "text": comment.get("textDisplay", ""),
                "published_at": comment.get("publishedAt"),
                "updated_at": comment.get("updatedAt"),
                "like_count": comment.get("likeCount", 0),
                "url": (
                    f"https://www.youtube.com/watch?v={video_id}"
                    f"&lc={comment_id}"
                )
            })

    return videos, comments

if __name__ == "__main__":
    # videos, comments = fetch_youtube_data(
    #     brand="Microsoft",
    #     max_videos=5,
    #     comments_per_video=20)
    pass