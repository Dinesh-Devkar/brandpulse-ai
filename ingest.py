
from database.init_db import init_db
from database.repository import save_brand_data

from youtube import fetch_youtube_data
from hacker_news import fetch_hacker_news_mentions


def ingest_brand(brand_name):

    brand_name = brand_name.strip()

    if not brand_name:
        raise ValueError("Brand name cannot be empty")

    # Step 1: Initialize database
    init_db()

    # Step 2: Fetch YouTube data
    print(f"Fetching YouTube data for {brand_name}...")

    videos, comments = fetch_youtube_data(
        brand=brand_name,
        max_videos=5,
        comments_per_video=20
    )

    # Step 3: Fetch Hacker News data
    print(f"Fetching Hacker News data for {brand_name}...")

    hn_items = fetch_hacker_news_mentions(
        brand=brand_name,
        max_results=20
    )

    # Step 4: Save unique records into SQL Server
    print("Checking duplicates and inserting data...")

    stats = save_brand_data(
        brand_name=brand_name,
        videos=videos,
        comments=comments,
        hn_items=hn_items
    )

    # Step 5: Display execution summary
    print("\nData Ingestion Completed!")

    print(f"YouTube videos fetched: {len(videos)}")
    print(f"YouTube comments fetched: {len(comments)}")
    print(f"Hacker News items fetched: {len(hn_items)}")

    print("\nNew records inserted:")
    print(f"YouTube videos: {stats['videos_inserted']}")
    print(f"YouTube comments: {stats['comments_inserted']}")
    print(f"Hacker News items: {stats['hn_items_inserted']}")

    print("\nNew brand associations:")
    print(f"Videos: {stats['video_links_created']}")
    print(f"Comments: {stats['comment_links_created']}")
    print(f"Hacker News: {stats['hn_links_created']}")

    return stats


if __name__ == "__main__":

    brand = input("Enter brand/company name: ")

    ingest_brand(brand)
