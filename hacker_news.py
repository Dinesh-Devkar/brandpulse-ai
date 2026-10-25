
import requests

from html.parser import HTMLParser
from progress_events import emit_progress


HACKER_NEWS_API_URL = (
    "https://hn.algolia.com/api/v1/search_by_date"
)


# =====================================================
# HELPER: CONVERT HTML TO PLAIN TEXT
# =====================================================
class HTMLTextExtractor(HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):

        if tag in ("p", "br", "div", "li"):
            self.parts.append(" ")

    def handle_data(self, data):
        self.parts.append(data)

    def get_text(self):
        return " ".join(
            "".join(self.parts).split()
        )


def clean_html(value):

    if not value:
        return ""

    parser = HTMLTextExtractor()
    parser.feed(str(value))

    return parser.get_text()


# =====================================================
# MAIN FUNCTION: FETCH HACKER NEWS MENTIONS
# =====================================================
def fetch_hacker_news_mentions(
    brand,
    max_results=20,
    progress_callback=None
):

    if not isinstance(brand, str) or not brand.strip():
        raise ValueError("Brand name cannot be empty")

    if type(max_results) is not int or max_results < 1:
        raise ValueError("max_results must be positive")

    if max_results > 1000:
        raise ValueError(
            "max_results cannot exceed 1000 "
            "in this single-request implementation"
        )

    brand = brand.strip()

    # =================================================
    # STEP 1: SEND SEARCH REQUEST
    # =================================================
    emit_progress(
        progress_callback,
        phase="ingestion",
        stage="hacker_news",
        status="running",
        message=(
            f"Searching Hacker News discussions "
            f"about {brand}..."
        )
    )

    params = {
        "query": brand,
        "tags": "(story,comment)",
        "hitsPerPage": max_results
    }

    response = requests.get(
        HACKER_NEWS_API_URL,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    hits = data.get("hits", [])

    # =================================================
    # STEP 2: REPORT SEARCH RESULTS
    # =================================================
    emit_progress(
        progress_callback,
        phase="ingestion",
        stage="hacker_news",
        status="running",
        message=(
            f"Hacker News returned "
            f"{len(hits)} search results."
        ),
        items_found=len(hits)
    )

    # =================================================
    # STEP 3: EXTRACT AND PREPARE RECORDS
    # =================================================
    hn_items = []

    for hit in hits:

        source_id = hit.get("objectID")

        if not source_id:
            continue

        tags = hit.get("_tags") or []

        if "comment" in tags:
            content_type = "comment"
        else:
            content_type = "story"

        # ---------------------------------------------
        # Extract content
        # ---------------------------------------------
        if content_type == "comment":

            text = clean_html(
                hit.get("comment_text")
            )

        else:

            title = clean_html(
                hit.get("title")
                or hit.get("story_title")
            )

            story_text = clean_html(
                hit.get("story_text")
            )

            text = " ".join(
                part
                for part in (title, story_text)
                if part
            )

        # Skip records without usable text
        if not text:
            continue

        # ---------------------------------------------
        # Parent item (mainly for comments)
        # ---------------------------------------------
        parent_id = hit.get("parent_id")

        if parent_id is not None:
            parent_id = int(parent_id)

        # ---------------------------------------------
        # Create normalized record
        # ---------------------------------------------
        hn_items.append({
            "brand": brand,
            "source": "hacker_news",
            "source_id": str(source_id),
            "content_type": content_type,
            "text": text,
            "parent_id": parent_id,
            "published_at": hit.get("created_at"),
            "url": (
                "https://news.ycombinator.com/"
                f"item?id={source_id}"
            )
        })

    # =================================================
    # STEP 4: REPORT PREPARED RECORDS
    # =================================================
    emit_progress(
        progress_callback,
        phase="ingestion",
        stage="hacker_news",
        status="running",
        message=(
            f"Prepared {len(hn_items)} Hacker News "
            "records for database storage."
        ),
        items_found=len(hits),
        items_prepared=len(hn_items)
    )

    # =================================================
    # FINAL RESULT
    # =================================================
    return hn_items
