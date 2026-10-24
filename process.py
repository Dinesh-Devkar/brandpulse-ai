"""Phase 1 orchestration: process mentions, persist insights, then summarize."""

import hashlib
import json

from database.init_db  import init_db
from database.analysis_repository import (
    get_brand_id,
    get_unprocessed_mentions,
    count_unprocessed_mentions,
    save_mention_analysis,
    brand_summary_exists,
    get_brand_summary_context,
    save_brand_summary,
)

# Replace with the model and prompt identifiers you actually use.
MODEL_NAME = "your_ollama_model"
ANALYSIS_PROMPT_VERSION = "v1"
ANALYSIS_SCHEMA_VERSION = "v2"  # Includes negative_feedback
SUMMARY_PROMPT_VERSION = "v1"


def analyze_mention_with_ollama(brand_name, mention):
    print("Ollama function called")
    print(brand_name)
    print("=========")
    print(mention)
    """Implement yourself. Return a Python dict, not a JSON string.

    
    Required shape:
    {
        "is_relevant": True,
        "overall_sentiment": "mixed",
        "product_name": "Microsoft Copilot",  # or None
        "topics": [
            {"topic": "Pricing", "sentiment": "negative",
             "explanation": "Subscription costs are high"},
            {"topic": "AI Features", "sentiment": "positive",
             "explanation": "Helpful capabilities"}
        ],
        "positive_feedback": [
            {"topic": "AI Features", "feedback": "Useful features",
             "type": "appreciation"}
        ],
        "negative_feedback": [
            {"topic": "Pricing", "feedback": "Price is too high",
             "type": "complaint"}
        ],
    }
    Feedback topics must appear in the 'topics' list, or be None.

    For irrelevant records: is_relevant=False, sentiment/product=None,
    and topics/positive_feedback/negative_feedback=[].
    """
    raise NotImplementedError("Implement analyze_mention_with_ollama")


def generate_brand_summary_with_ollama(brand_name, context):
    """Implement yourself. Return a Python dict with string values:

    {
        "executive_summary": "...",
        "positive_highlights": "...",
        "negative_highlights": "...",
        "strengths_summary": "...",
    }

    context includes sentiment_counts, top_topics, positive_feedback,
    negative_feedback, relevant_mentions_count, and evidence.
    """
    raise NotImplementedError("Implement generate_brand_summary_with_ollama")


def content_hash(brand_name, mention):
    """Fingerprint the exact brand-specific content and context analyzed."""
    data = {
        "brand": brand_name.strip().casefold(),
        "source": mention["source"],
        "source_id": mention["source_id"],
        "text": mention["text"],
        "context": mention.get("context"),
    }
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def process_brand(brand_name, max_records=100):
    if not isinstance(brand_name, str) or not brand_name.strip():
        raise ValueError("brand_name must be a nonempty string")
    if type(max_records) is not int or max_records < 1:
        raise ValueError("max_records must be a positive integer")

    brand_name = brand_name.strip()
    init_db()
    brand_id = get_brand_id(brand_name)
    if brand_id is None:
        raise ValueError(f"Brand {brand_name!r} not found. Run ingest.py first.")

    pending_before = count_unprocessed_mentions(brand_id)
    mentions = get_unprocessed_mentions(brand_id, limit=max_records)
    stats = {
        "brand": brand_name,
        "pending_before": pending_before,
        "selected": len(mentions),
        "analyzed": 0,
        "skipped": 0,
        "failed": 0,
        "remaining": None,
        "summary_status": "not_started",
    }

    print('STATS : \n')
    print(stats)
    print("========================================")
    print(mentions)

    for index, mention in enumerate(mentions, start=1):
        print(f"[{index}/{len(mentions)}] {mention['source']} {mention['source_id']}")
        try:
            # Your Ollama implementation returns the specified dictionary.
            result = analyze_mention_with_ollama(brand_name, mention)
            saved = save_mention_analysis(
                brand_id=brand_id,
                mention=mention,
                result=result,
                content_hash=content_hash(brand_name, mention),
                model_name=MODEL_NAME,
                prompt_version=ANALYSIS_PROMPT_VERSION,
                schema_version=ANALYSIS_SCHEMA_VERSION,
            )
            stats["analyzed" if saved else "skipped"] += 1
        except NotImplementedError:
            raise  # Make unfinished AI functions obvious.
        except Exception as exc:
            stats["failed"] += 1
            print(f"  Failed: {exc}")  # This record remains eligible for retry.

    stats["remaining"] = count_unprocessed_mentions(brand_id)

    # Phase 1: only generate the FIRST summary, after all source records are analyzed.
    if brand_summary_exists(brand_id):
        stats["summary_status"] = "already_exists"
    elif stats["remaining"] > 0:
        stats["summary_status"] = "deferred_pending_records"
    else:
        context = get_brand_summary_context(brand_id)
        if context["relevant_mentions_count"] == 0:
            stats["summary_status"] = "no_relevant_mentions"
        else:
            try:
                summary = generate_brand_summary_with_ollama(brand_name, context)
                saved = save_brand_summary(
                    brand_id=brand_id,
                    summary=summary,
                    context=context,
                    model_name=MODEL_NAME,
                    prompt_version=SUMMARY_PROMPT_VERSION,
                )
                stats["summary_status"] = "generated" if saved else "already_exists"
            except NotImplementedError:
                raise
            except Exception as exc:
                stats["summary_status"] = "failed"
                print(f"Summary generation failed: {exc}")

    print(json.dumps(stats, indent=2))
    return stats


if __name__ == "__main__":
    brand = input("Enter brand/company name: ").strip()
    process_brand(brand, max_records=100)
