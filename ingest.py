
import json

from database.init_db import init_db
from database.repository import save_brand_data

from youtube import fetch_youtube_data
from hacker_news import fetch_hacker_news_mentions

from progress_events import emit_progress


# =====================================================
# MAIN FUNCTION: BRAND INGESTION
# =====================================================
def ingest_brand(
    brand_name,
    progress_callback=None,
    max_videos=5,
    comments_per_video=20,
    hn_max_results=20
):

    if not isinstance(brand_name, str) or not brand_name.strip():
        raise ValueError("Brand name cannot be empty")

    brand_name = brand_name.strip()

    current_stage = "database"

    try:

        # =============================================
        # STEP 1: INITIALIZE DATABASE
        # =============================================
        emit_progress(
            progress_callback,
            phase="ingestion",
            stage="database",
            status="started",
            message="Initializing BrandPulseDB..."
        )

        init_db()

        emit_progress(
            progress_callback,
            phase="ingestion",
            stage="database",
            status="completed",
            message="Database initialized successfully."
        )

        # =============================================
        # STEP 2: FETCH YOUTUBE DATA
        # =============================================
        current_stage = "youtube"

        emit_progress(
            progress_callback,
            phase="ingestion",
            stage="youtube",
            status="started",
            message="Starting YouTube data collection..."
        )

        videos, comments = fetch_youtube_data(
            brand=brand_name,
            max_videos=max_videos,
            comments_per_video=comments_per_video,
            progress_callback=progress_callback
        )

        emit_progress(
            progress_callback,
            phase="ingestion",
            stage="youtube",
            status="completed",
            message="YouTube data collection completed.",
            videos_fetched=len(videos),
            comments_fetched=len(comments)
        )

        # =============================================
        # STEP 3: FETCH HACKER NEWS DATA
        # =============================================
        current_stage = "hacker_news"

        emit_progress(
            progress_callback,
            phase="ingestion",
            stage="hacker_news",
            status="started",
            message="Starting Hacker News data collection..."
        )

        hn_items = fetch_hacker_news_mentions(
            brand=brand_name,
            max_results=hn_max_results,
            progress_callback=progress_callback
        )

        emit_progress(
            progress_callback,
            phase="ingestion",
            stage="hacker_news",
            status="completed",
            message="Hacker News data collection completed.",
            items_fetched=len(hn_items)
        )

        # =============================================
        # STEP 4: DATABASE STORAGE AND DEDUPLICATION
        # =============================================
        current_stage = "storage"

        emit_progress(
            progress_callback,
            phase="ingestion",
            stage="storage",
            status="started",
            message=(
                "Checking existing source records, "
                "filtering duplicates and saving "
                "brand associations..."
            )
        )

        # Existing database repository function.
        # Its insertion and duplicate filtering
        # logic remains unchanged.
        summary = save_brand_data(
            brand_name,
            videos,
            comments,
            hn_items
        )

        # Actual counts from SQL Server insertions
        stats = (
            summary
            if isinstance(summary, dict)
            else {}
        )

        new_comments = stats.get(
            "comments_inserted", 0
        )

        new_hn_items = stats.get(
            "hn_items_inserted", 0
        )

        total_fetched_mentions = (
            len(comments) + len(hn_items)
        )

        new_raw_mentions = (
            new_comments + new_hn_items
        )

        existing_raw_mentions = (
            total_fetched_mentions
            - new_raw_mentions
        )

        emit_progress(
            progress_callback,
            phase="ingestion",
            stage="storage",
            status="completed",
            message=(
                "Database storage and duplicate "
                "filtering completed successfully."
            ),
            videos_inserted=stats.get(
                "videos_inserted", 0
            ),
            comments_inserted=new_comments,
            hn_items_inserted=new_hn_items,
            video_links_created=stats.get(
                "video_links_created", 0
            ),
            comment_links_created=stats.get(
                "comment_links_created", 0
            ),
            hn_links_created=stats.get(
                "hn_links_created", 0
            ),
            new_raw_mentions=new_raw_mentions,
            existing_raw_mentions=existing_raw_mentions
        )

        # =============================================
        # STEP 5: INGESTION COMPLETED
        # =============================================
        current_stage = "completed"

        emit_progress(
            progress_callback,
            phase="ingestion",
            stage="completed",
            status="completed",
            message=(
                f"Brand mention collection completed "
                f"for {brand_name}. "
                "Ready for AI processing."
            ),
            videos_fetched=len(videos),
            youtube_comments_fetched=len(comments),
            hacker_news_items_fetched=len(hn_items),
            total_mentions_fetched=total_fetched_mentions,
            new_raw_mentions=new_raw_mentions,
            existing_raw_mentions=existing_raw_mentions
        )

        # Keep the original repository return format
        return summary

    except Exception as error:

        emit_progress(
            progress_callback,
            phase="ingestion",
            stage=current_stage,
            status="failed",
            message=(
                f"Ingestion failed during "
                f"{current_stage}."
            ),
            error_type=type(error).__name__
        )

        raise


# =====================================================
# EXECUTE SCRIPT
# =====================================================
if __name__ == "__main__":

    brand = input(
        "Enter brand/company name: "
    ).strip()

    def show_progress(event):

        print(
            f"[{event['stage'].upper()}] "
            f"{event['status']} - "
            f"{event['message']}"
        )

        if event["metrics"]:
            print("Metrics:", event["metrics"])

    result = ingest_brand(
        brand_name=brand,
        progress_callback=show_progress,
        max_videos=5,
        comments_per_video=20,
        hn_max_results=20
    )

    print("\n========== INGESTION SUMMARY ==========")

    print(json.dumps(
        result,
        indent=2,
        default=str
    ))
