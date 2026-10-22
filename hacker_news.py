
import requests
from bs4 import BeautifulSoup


def fetch_hacker_news_mentions(brand, max_results=20):
    url = "https://hn.algolia.com/api/v1/search_by_date"

    params = {
        "query": brand,
        "tags": "(story,comment)",
        "hitsPerPage": max_results
    }

    response = requests.get(
        url,
        params=params,
        timeout=30
    )
    response.raise_for_status()

    hits = response.json().get("hits", [])

    records = []

    for item in hits:
        tags = item.get("_tags", [])

        if "comment" in tags:
            content_type = "comment"
            raw_text = item.get("comment_text") or ""
        else:
            content_type = "story"
            title = item.get("title") or ""
            body = item.get("story_text") or ""
            raw_text = f"{title} {body}"

        clean_text = BeautifulSoup(
            raw_text, "html.parser"
        ).get_text(" ", strip=True)

        if not clean_text:
            continue

        records.append({
            "brand": brand,
            "source": "hacker_news",
            "source_id": item["objectID"],
            "content_type": content_type,
            "text": clean_text,
            "published_at": item.get("created_at"),
            "url": (
                f"https://news.ycombinator.com/"
                f"item?id={item['objectID']}"
            )
        })

    return records


if __name__ == "__main__":
    pass
    # brand = "Microsoft"

    # data = fetch_hacker_news_mentions(
    #     brand=brand,
    #     max_results=20
    # )

    # print(f"Fetched {len(data)} Hacker News records")

    # for record in data[:3]:
    #     print(record)
    #     print("\n" + "===========================" + "\n")
