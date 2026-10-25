
from datetime import datetime, timezone


def emit_progress(
    callback,
    phase,
    stage,
    status,
    message,
    **metrics
):
    """
    Emit a structured backend progress event.

    callback:
        Optional function that receives an event dict.

    phase:
        ingestion / analysis

    stage:
        database / youtube / hacker_news /
        storage / completed / ...

    status:
        started / running / completed / failed

    message:
        Human-readable backend update.

    metrics:
        Optional actual counters returned by backend.
    """

    if callback is None:
        return

    event = {
        "phase": phase,
        "stage": stage,
        "status": status,
        "message": message,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "metrics": metrics
    }

    callback(event)
