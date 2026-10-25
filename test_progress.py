
from ingest import ingest_brand


def on_progress(event):

    print(
        f"[{event['stage'].upper()}] "
        f"{event['status']} — "
        f"{event['message']}"
    )

    if event["metrics"]:
        print("Metrics:", event["metrics"])


result = ingest_brand(
    brand_name="Microsoft",
    progress_callback=on_progress
)
