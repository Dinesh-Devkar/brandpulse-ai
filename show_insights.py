
import json

from database.analysis_repository import get_brand_id

from database.insights_repository import (
    get_brand_overview,
    get_sentiment_distribution,
    get_source_wise_sentiment,
    get_sentiment_trend,
    get_topic_intelligence,
    get_positive_feedback,
    get_negative_feedback,
    get_executive_summary
)


# =====================================================
# MAIN FUNCTION: SHOW BRAND INSIGHTS
# =====================================================
def show_insights(
    brand_name: str,
    topic_limit: int = 10,
    feedback_limit: int = 20,
    trend_granularity: str = "month"
) -> dict:

    # ---------------------------------------------
    # 1. VALIDATE INPUTS
    # ---------------------------------------------
    if not isinstance(brand_name, str) or not brand_name.strip():
        raise ValueError("Brand name cannot be empty")

    brand_name = brand_name.strip()

    if type(topic_limit) is not int or topic_limit <= 0:
        raise ValueError("topic_limit must be a positive integer")

    if type(feedback_limit) is not int or feedback_limit <= 0:
        raise ValueError("feedback_limit must be a positive integer")

    if trend_granularity not in ("week", "month"):
        raise ValueError(
            "trend_granularity must be 'week' or 'month'"
        )

    # ---------------------------------------------
    # 2. GET BRAND ID
    # ---------------------------------------------
    brand_id = get_brand_id(brand_name)

    if brand_id is None:
        raise ValueError(
            f"Brand '{brand_name}' not found in database. "
            "Please ingest the brand data first."
        )

    # ---------------------------------------------
    # 3. GET BRAND OVERVIEW
    # ---------------------------------------------
    overview = get_brand_overview(brand_id)

    # ---------------------------------------------
    # 4. GET SENTIMENT DISTRIBUTION
    # ---------------------------------------------
    sentiment_distribution = (
        get_sentiment_distribution(brand_id)
    )

    # ---------------------------------------------
    # 5. GET SOURCE-WISE SENTIMENT
    # ---------------------------------------------
    source_wise_sentiment = (
        get_source_wise_sentiment(brand_id)
    )

    # ---------------------------------------------
    # 6. GET SENTIMENT TREND
    # ---------------------------------------------
    sentiment_trend = get_sentiment_trend(
        brand_id=brand_id,
        granularity=trend_granularity
    )

    # ---------------------------------------------
    # 7. GET TOPIC INTELLIGENCE
    # ---------------------------------------------
    topic_intelligence = get_topic_intelligence(
        brand_id=brand_id,
        limit=topic_limit
    )

    # ---------------------------------------------
    # 8. GET POSITIVE FEEDBACK
    # ---------------------------------------------
    positive_feedback = get_positive_feedback(
        brand_id=brand_id,
        limit=feedback_limit
    )

    # ---------------------------------------------
    # 9. GET NEGATIVE FEEDBACK
    # ---------------------------------------------
    negative_feedback = get_negative_feedback(
        brand_id=brand_id,
        limit=feedback_limit
    )

    # ---------------------------------------------
    # 10. GET SAVED EXECUTIVE SUMMARY
    # ---------------------------------------------
    executive_summary = get_executive_summary(
        brand_id=brand_id
    )

    # ---------------------------------------------
    # 11. COMBINE ALL INSIGHTS
    # ---------------------------------------------
    insights = {
        "brand": brand_name,
        "brand_id": brand_id,

        "overview": overview,

        "sentiment_distribution": sentiment_distribution,

        "source_wise_sentiment": source_wise_sentiment,

        "sentiment_trend": sentiment_trend,

        "topic_intelligence": topic_intelligence,

        "positive_feedback": positive_feedback,

        "negative_feedback": negative_feedback,

        "executive_summary": executive_summary,

        "metadata": {
            "trend_granularity": trend_granularity,
            "topic_limit": topic_limit,
            "feedback_limit": feedback_limit,
            "summary_available": executive_summary is not None
        }
    }

    return insights


# =====================================================
# SCRIPT EXECUTION
# =====================================================
if __name__ == "__main__":

    brand_name = input("Enter brand name: ").strip()

    insights = show_insights(
        brand_name=brand_name,
        topic_limit=10,
        feedback_limit=20,
        trend_granularity="month"
    )

    print(json.dumps(
        insights,
        indent=2,
        ensure_ascii=False
    ))
