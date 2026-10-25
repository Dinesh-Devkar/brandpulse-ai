"""Progress-enabled BrandPulse AI processing orchestration.

Reuses the existing Ollama functions in process.py without changing them.
"""

import json

from database.init_db import init_db
from database.analysis_repository import (
    get_brand_id,
    get_unprocessed_mentions,
    count_unprocessed_mentions,
    save_mention_analysis,
    brand_summary_exists,
    get_brand_summary_context,
    save_brand_summary,
)
from progress_events import emit_progress
from process import (
    analyze_mention_with_ollama,
    generate_brand_summary_with_ollama,
    content_hash,
    MODEL_NAME,
    ANALYSIS_PROMPT_VERSION,
    ANALYSIS_SCHEMA_VERSION,
    SUMMARY_PROMPT_VERSION,
)


def process_brand_with_progress(
    brand_name,
    max_records=100,
    progress_callback=None,
):
    """Process pending brand mentions and emit live progress events.

    Returns the same statistics dictionary as the existing process_brand().
    Progress percentages describe records attempted in this batch, not
    completion of all pending mentions or the duration of summary generation.
    """
    if not isinstance(brand_name, str) or not brand_name.strip():
        raise ValueError("brand_name must be a nonempty string")
    if type(max_records) is not int or max_records < 1:
        raise ValueError("max_records must be a positive integer")

    brand_name = brand_name.strip()
    current_stage = "database"

    try:
        emit_progress(
            progress_callback,
            phase="analysis",
            stage="database",
            status="started",
            message="Preparing database for AI analysis...",
        )
        init_db()
        brand_id = get_brand_id(brand_name)
        if brand_id is None:
            raise ValueError(
                f"Brand {brand_name!r} not found. Run ingest_brand() first."
            )

        emit_progress(
            progress_callback,
            phase="analysis",
            stage="database",
            status="completed",
            message="Database is ready for AI analysis.",
            brand_id=brand_id,
        )

        current_stage = "loading"
        emit_progress(
            progress_callback,
            phase="analysis",
            stage="loading",
            status="started",
            message="Finding brand mentions without saved AI insights...",
        )
        pending_before = count_unprocessed_mentions(brand_id)
        mentions = get_unprocessed_mentions(brand_id, limit=max_records)
        total_selected = len(mentions)

        stats = {
            "brand": brand_name,
            "pending_before": pending_before,
            "selected": total_selected,
            "analyzed": 0,
            "skipped": 0,
            "failed": 0,
            "remaining": None,
            "summary_status": "not_started",
        }
        extracted = {
            "relevant_analyzed": 0,
            "topics_extracted": 0,
            "positive_feedback_extracted": 0,
            "negative_feedback_extracted": 0,
        }

        emit_progress(
            progress_callback,
            phase="analysis",
            stage="loading",
            status="completed",
            message=f"Selected {total_selected} of {pending_before} pending mentions.",
            pending_before=pending_before,
            records_selected=total_selected,
        )

        current_stage = "records"
        if total_selected:
            emit_progress(
                progress_callback,
                phase="analysis",
                stage="records",
                status="started",
                message=f"Starting AI analysis of {total_selected} mentions...",
                records_total=total_selected,
                records_processed=0,
                batch_progress_percentage=0.0,
            )

        for index, mention in enumerate(mentions, start=1):
            source_id = mention["source_id"]
            source = mention["source"]

            emit_progress(
                progress_callback,
                phase="analysis",
                stage="records",
                status="running",
                message=f"Analyzing {source} mention {index}/{total_selected}...",
                records_total=total_selected,
                records_processed=index - 1,
                batch_progress_percentage=round(
                    (index - 1) / total_selected * 100, 2
                ),
                current_source=source,
            )

            try:
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

                if saved:
                    stats["analyzed"] += 1
                    if result["is_relevant"]:
                        extracted["relevant_analyzed"] += 1
                        extracted["topics_extracted"] += len(result["topics"])
                        extracted["positive_feedback_extracted"] += len(
                            result["positive_feedback"]
                        )
                        extracted["negative_feedback_extracted"] += len(
                            result["negative_feedback"]
                        )
                else:
                    stats["skipped"] += 1

            except NotImplementedError:
                # Preserve the existing behavior for unfinished AI functions.
                raise
            except Exception as exc:
                stats["failed"] += 1
                emit_progress(
                    progress_callback,
                    phase="analysis",
                    stage="records",
                    status="failed",
                    message=f"Could not process {source} mention {source_id}.",
                    error_type=type(exc).__name__,
                    recoverable=True,
                )

            emit_progress(
                progress_callback,
                phase="analysis",
                stage="records",
                status="running",
                message=f"Processed {index}/{total_selected} mentions.",
                records_total=total_selected,
                records_processed=index,
                batch_progress_percentage=round(index / total_selected * 100, 2),
                analyzed=stats["analyzed"],
                skipped=stats["skipped"],
                failed=stats["failed"],
                **extracted,
            )

        if total_selected:
            emit_progress(
                progress_callback,
                phase="analysis",
                stage="records",
                status="completed",
                message="AI analysis batch finished; checking remaining records...",
                records_total=total_selected,
                records_processed=total_selected,
                batch_progress_percentage=100.0,
                analyzed=stats["analyzed"],
                skipped=stats["skipped"],
                failed=stats["failed"],
                **extracted,
            )

        current_stage = "summary"
        stats["remaining"] = count_unprocessed_mentions(brand_id)

        if brand_summary_exists(brand_id):
            stats["summary_status"] = "already_exists"
            message = "Using the brand's existing executive summary."

        elif stats["remaining"] > 0:
            stats["summary_status"] = "deferred_pending_records"
            message = (
                f"Summary deferred: {stats['remaining']} mentions still "
                "require analysis."
            )

        else:
            context = get_brand_summary_context(brand_id)
            if context["relevant_mentions_count"] == 0:
                stats["summary_status"] = "no_relevant_mentions"
                message = "No relevant mentions available for a summary."
            else:
                emit_progress(
                    progress_callback,
                    phase="analysis",
                    stage="summary",
                    status="started",
                    message="Generating the initial executive brand summary...",
                    relevant_mentions_count=context["relevant_mentions_count"],
                )
                try:
                    summary = generate_brand_summary_with_ollama(
                        brand_name, context
                    )
                    saved = save_brand_summary(
                        brand_id=brand_id,
                        summary=summary,
                        context=context,
                        model_name=MODEL_NAME,
                        prompt_version=SUMMARY_PROMPT_VERSION,
                    )
                    stats["summary_status"] = (
                        "generated" if saved else "already_exists"
                    )
                    message = "Executive summary saved successfully."
                except NotImplementedError:
                    raise
                except Exception as exc:
                    stats["summary_status"] = "failed"
                    message = "Executive summary generation failed."
                    emit_progress(
                        progress_callback,
                        phase="analysis",
                        stage="summary",
                        status="failed",
                        message=message,
                        error_type=type(exc).__name__,
                    )

        if stats["summary_status"] != "failed":
            emit_progress(
                progress_callback,
                phase="analysis",
                stage="summary",
                status="completed",
                message=message,
                summary_status=stats["summary_status"],
                remaining=stats["remaining"],
            )

        current_stage = "completed"
        emit_progress(
            progress_callback,
            phase="analysis",
            stage="completed",
            status="completed",
            message=(
                "AI processing run finished."
                if stats["failed"] == 0 and stats["summary_status"] != "failed"
                else "AI processing run finished with errors."
            ),
            **stats,
            **extracted,
        )
        return stats

    except Exception as exc:
        emit_progress(
            progress_callback,
            phase="analysis",
            stage=current_stage,
            status="failed",
            message=f"AI processing stopped during {current_stage}.",
            error_type=type(exc).__name__,
            recoverable=False,
        )
        raise


if __name__ == "__main__":
    brand = input("Enter brand/company name: ").strip()

    def print_event(event):
        print(f"[{event['stage'].upper()}] {event['status']}: {event['message']}")
        if event["metrics"]:
            print("  ", event["metrics"])

    result = process_brand_with_progress(
        brand_name=brand,
        max_records=20,
        progress_callback=print_event,
    )
    print(json.dumps(result, indent=2))
