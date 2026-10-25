
from typing import Literal
from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    StrictBool,
    model_validator
)


# Common sentiment categories
Sentiment = Literal[
    "positive",
    "negative",
    "neutral",
    "mixed"
]


# -------------------------------------------------
# 1. TOPIC ANALYSIS
# -------------------------------------------------
class TopicAnalysis(BaseModel):

    topic: str = Field(
        description="Standardized topic name such as Pricing, Performance, AI Features or Customer Support.",
        min_length=1,
        max_length=150
    )

    sentiment: Sentiment = Field(
        description="Sentiment specifically toward this topic."
    )

    explanation: str = Field(
        description="Brief explanation of what the user says about this topic.",
        min_length=1
    )


# -------------------------------------------------
# 2. POSITIVE FEEDBACK
# -------------------------------------------------
class PositiveFeedback(BaseModel):

    topic: str | None = Field(
        description="Related topic from the topics list, or null if no topic applies."
    )

    feedback: str = Field(
        description="Specific positive feedback or appreciation expressed by the user.",
        min_length=1,
        max_length=1000
    )

    type: Literal[
        "appreciation",
        "expansion_request"
    ] = Field(
        description="Type of positive feedback."
    )


# -------------------------------------------------
# 3. NEGATIVE FEEDBACK
# -------------------------------------------------
class NegativeFeedback(BaseModel):

    topic: str | None = Field(
        description="Related topic from the topics list, or null if no topic applies."
    )

    feedback: str = Field(
        description="Specific complaint, limitation or concern expressed by the user.",
        min_length=1,
        max_length=1000
    )

    type: Literal[
        "complaint",
        "limitation",
        "concern"
    ] = Field(
        description="Type of negative feedback."
    )


# -------------------------------------------------
# 4. MAIN BRAND ANALYSIS OUTPUT
# -------------------------------------------------
class BrandMentionAnalysisOutput(BaseModel):

    model_config = ConfigDict(extra="forbid")

    is_relevant: StrictBool = Field(
        description="True if the content genuinely discusses the target brand or its products. Otherwise false."
    )

    overall_sentiment: Sentiment | None = Field(
        description="Overall sentiment toward the target brand. Null if irrelevant."
    )

    product_name: str | None = Field(
        description="Main product or service of the target brand being discussed. Null if not identifiable.",
        max_length=200
    )

    topics: list[TopicAnalysis] = Field(
        description="All distinct topics discussed, with their individual sentiments."
    )

    positive_feedback: list[PositiveFeedback] = Field(
        description="Positive observations explicitly supported by the text. Empty list if none."
    )

    negative_feedback: list[NegativeFeedback] = Field(
        description="Negative observations explicitly supported by the text. Empty list if none."
    )

    @model_validator(mode="after")
    def validate_analysis(self):

        # Irrelevant mentions should not contain
        # sentiment, product, topics or feedback.
        if not self.is_relevant:

            if (
                self.overall_sentiment is not None
                or self.product_name is not None
                or self.topics
                or self.positive_feedback
                or self.negative_feedback
            ):
                raise ValueError(
                    "Irrelevant records must have null sentiment/product "
                    "and empty topics and feedback lists."
                )

            return self

        # Relevant mentions require overall sentiment.
        if self.overall_sentiment is None:
            raise ValueError(
                "Relevant records must have overall_sentiment."
            )

        # Avoid duplicate topic names.
        topic_names = [t.topic.casefold() for t in self.topics]

        if len(topic_names) != len(set(topic_names)):
            raise ValueError("Duplicate topics are not allowed.")

        # Feedback topics must exist in the topics list.
        valid_topics = set(topic_names)

        for item in self.positive_feedback + self.negative_feedback:

            if (
                item.topic is not None
                and item.topic.casefold() not in valid_topics
            ):
                raise ValueError(
                    f"Feedback topic '{item.topic}' is not in topics list."
                )

        return self




from pydantic import BaseModel, Field, ConfigDict


class BrandExecutiveSummaryOutput(BaseModel):

    model_config = ConfigDict(extra="forbid")

    executive_summary: str = Field(
        description=(
            "Concise, balanced executive summary of the target brand's "
            "perception across analyzed online discussions. Include "
            "the overall sentiment, major discussion themes, key "
            "strengths, and key concerns. Base conclusions strictly "
            "on the supplied data."
        ),
        min_length=1
    )

    positive_highlights: str = Field(
        description=(
            "Summary of the main positive observations, appreciated "
            "features, favorable experiences, and positive feedback "
            "supported by the analyzed discussions."
        ),
        min_length=1
    )

    negative_highlights: str = Field(
        description=(
            "Summary of the main complaints, negative experiences, "
            "limitations, and concerns supported by the analyzed "
            "discussions."
        ),
        min_length=1
    )

    strengths_summary: str = Field(
        description=(
            "Synthesis of the target brand's demonstrated strengths "
            "based on recurring positive themes and supporting "
            "feedback, without introducing unsupported claims."
        ),
        min_length=1
    )
