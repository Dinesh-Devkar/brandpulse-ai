
import os
import requests

from dotenv import load_dotenv
from progress_events import emit_progress


load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

YOUTUBE_SEARCH_URL = (
    "https://www.googleapis.com/youtube/v3/search"
)

YOUTUBE_COMMENTS_URL = (
    "https://www.googleapis.com/youtube/v3/commentThreads"
)


# =====================================================
# HELPER: MAKE YOUTUBE API REQUEST
# =====================================================
def youtube_api_request(url, params):

    if not YOUTUBE_API_KEY:
        raise ValueError(
            "YOUTUBE_API_KEY is missing in .env"
        )

    params = {
        **params,
        "key": YOUTUBE_API_KEY
    }

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    if not response.ok:

        try:
            error_data = response.json()
            errors = error_data.get("error", {}).get(
                "errors", []
            )

            reason = (
                errors[0].get("reason", "unknown")
                if errors else "unknown"
            )

        except ValueError:
            reason = "unknown"

        # Do not expose the full request URL because
        # it contains the YouTube API key.
        raise RuntimeError(
            f"YouTube API error: HTTP "
            f"{response.status_code} ({reason})"
        )

    return response.json()


# =====================================================
# MAIN FUNCTION: FETCH YOUTUBE DATA
# =====================================================
def fetch_youtube_data(
    brand,
    max_videos=5,
    comments_per_video=20,
    progress_callback=None
):

    if not isinstance(brand, str) or not brand.strip():
        raise ValueError("Brand name cannot be empty")

    if type(max_videos) is not int or max_videos < 1:
        raise ValueError("max_videos must be positive")

    if (
        type(comments_per_video) is not int
        or comments_per_video < 1
    ):
        raise ValueError(
            "comments_per_video must be positive"
        )

    brand = brand.strip()

    videos = []
    comments = []

    # =================================================
    # STEP 1: SEARCH YOUTUBE VIDEOS
    # =================================================
    emit_progress(
        progress_callback,
        phase="ingestion",
        stage="youtube",
        status="running",
        message=f"Searching YouTube videos about {brand}..."
    )

    next_page_token = None

    while len(videos) < max_videos:

        remaining = max_videos - len(videos)

        params = {
            "part": "snippet",
            "q": brand,
            "type": "video",
            "maxResults": min(remaining, 50),
            "order": "relevance"
        }

        if next_page_token:
            params["pageToken"] = next_page_token

        data = youtube_api_request(
            YOUTUBE_SEARCH_URL,
            params
        )

        for item in data.get("items", []):

            video_id = item.get("id", {}).get(
                "videoId"
            )

            if not video_id:
                continue

            snippet = item.get("snippet", {})

            videos.append({
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get(
                    "description", ""
                ),
                "channel_title": snippet.get(
                    "channelTitle"
                ),
                "published_at": snippet.get(
                    "publishedAt"
                ),
                "url": (
                    f"https://www.youtube.com/"
                    f"watch?v={video_id}"
                )
            })

        next_page_token = data.get("nextPageToken")

        if not next_page_token:
            break

    total_videos = len(videos)

    emit_progress(
        progress_callback,
        phase="ingestion",
        stage="youtube",
        status="running",
        message=(
            f"Discovered {total_videos} YouTube videos."
        ),
        videos_discovered=total_videos,
        videos_processed=0,
        videos_total=total_videos,
        comments_fetched=0
    )

    # =================================================
    # STEP 2: FETCH COMMENTS FOR EACH VIDEO
    # =================================================
    for video_index, video in enumerate(
        videos,
        start=1
    ):

        video_id = video["video_id"]

        emit_progress(
            progress_callback,
            phase="ingestion",
            stage="youtube",
            status="running",
            message=(
                f"Fetching comments from video "
                f"{video_index}/{total_videos}..."
            ),
            videos_processed=video_index - 1,
            videos_total=total_videos,
            comments_fetched=len(comments),
            current_video_id=video_id
        )

        fetched_for_video = 0
        next_page_token = None
        skipped_reason = None

        while fetched_for_video < comments_per_video:

            remaining = (
                comments_per_video - fetched_for_video
            )

            params = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": min(remaining, 100),
                "textFormat": "plainText"
            }

            if next_page_token:
                params["pageToken"] = next_page_token

            try:
                data = youtube_api_request(
                    YOUTUBE_COMMENTS_URL,
                    params
                )

            except RuntimeError as error:

                # Some videos have comments disabled.
                # Skip those videos, but do not hide
                # authentication or quota failures.
                if (
                    "(commentsDisabled)" in str(error)
                    or "(videoNotFound)" in str(error)
                ):
                    skipped_reason = str(error)
                    break

                raise

            items = data.get("items", [])

            for item in items:

                top_comment = (
                    item.get("snippet", {})
                    .get("topLevelComment", {})
                )

                comment_id = top_comment.get("id")

                if not comment_id:
                    continue

                snippet = top_comment.get(
                    "snippet", {}
                )

                comments.append({
                    "comment_id": comment_id,
                    "video_id": video_id,
                    "text": snippet.get(
                        "textDisplay", ""
                    ),
                    "published_at": snippet.get(
                        "publishedAt"
                    ),
                    "updated_at": snippet.get(
                        "updatedAt"
                    ),
                    "like_count": snippet.get(
                        "likeCount", 0
                    ),
                    "url": (
                        f"https://www.youtube.com/"
                        f"watch?v={video_id}"
                        f"&lc={comment_id}"
                    )
                })

                fetched_for_video += 1

                if (
                    fetched_for_video
                    >= comments_per_video
                ):
                    break

            next_page_token = data.get(
                "nextPageToken"
            )

            if not next_page_token or not items:
                break

        # =============================================
        # STEP 3: REPORT PROGRESS FOR THIS VIDEO
        # =============================================
        if skipped_reason:

            emit_progress(
                progress_callback,
                phase="ingestion",
                stage="youtube",
                status="running",
                message=(
                    f"Skipped comments for video "
                    f"{video_index}: comments unavailable."
                ),
                videos_processed=video_index,
                videos_total=total_videos,
                comments_fetched=len(comments),
                current_video_id=video_id,
                warning=skipped_reason
            )

        emit_progress(
            progress_callback,
            phase="ingestion",
            stage="youtube",
            status="running",
            message=(
                f"Processed video {video_index} "
                f"of {total_videos}. "
                f"Collected {len(comments)} comments so far."
            ),
            videos_processed=video_index,
            videos_total=total_videos,
            comments_fetched=len(comments),
            video_progress_percentage=round(
                video_index / total_videos * 100,
                2
            )
        )

    # =================================================
    # FINAL RESULT
    # =================================================
    return videos, comments
