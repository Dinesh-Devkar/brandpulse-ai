
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


def fetch_youtube_comments(brand, max_videos=5, comments_per_video=20):

    if not API_KEY:
        raise ValueError("YOUTUBE_API_KEY is missing from .env")

    # Step 1: Search for brand-related videos
    search_params = {
        "key": API_KEY,
        "part": "snippet",
        "q": brand,
        "type": "video",
        "maxResults": max_videos
    }

    response = requests.get(
        SEARCH_URL,
        params=search_params,
        timeout=30
    )
    response.raise_for_status()

    videos = response.json().get("items", [])

    records = []

    # Step 2: Fetch comments from each video
    for video in videos:
        video_id = video["id"]["videoId"]
        video_title = video["snippet"]["title"]

        comment_params = {
            "key": API_KEY,
            "part": "snippet",
            "videoId": video_id,
            "maxResults": comments_per_video,
            "textFormat": "plainText"
        }

        comment_response = requests.get(
            COMMENTS_URL,
            params=comment_params,
            timeout=30
        )

        # Skip only videos where comments are disabled
        if comment_response.status_code == 403:
            errors = comment_response.json().get(
                "error", {}
            ).get("errors", [])

            if any(
                error.get("reason") == "commentsDisabled"
                for error in errors
            ):
                continue

        comment_response.raise_for_status()

        comments = comment_response.json().get("items", [])

        for item in comments:
            top_comment = item["snippet"]["topLevelComment"]
            snippet = top_comment["snippet"]

            records.append({
                "brand": brand,
                "source": "youtube",
                "source_id": top_comment["id"],
                "content_type": "comment",
                "video_id": video_id,
                "video_title": video_title,
                "text": snippet["textDisplay"],
                "published_at": snippet["publishedAt"],
                "url": (
                    f"https://www.youtube.com/watch?v={video_id}"
                    f"&lc={top_comment['id']}"
                )
            })

    return records


if __name__ == "__main__":
    brand = "Microsoft"

    data = fetch_youtube_comments(
        brand=brand,
        max_videos=5,
        comments_per_video=20
    )


    print(f"Fetched {len(data)} YouTube comments")

    for record in data[:3]:
        print(record)
