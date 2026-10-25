"""BrandPulse Aurora — SQL-backed intelligence dashboard and drilldowns.

Uses the existing show_insights() orchestration; no scraping, database writes,
or LLM calls occur here. Navigation is client-side Streamlit session state.
"""
from __future__ import annotations

from html import escape
from urllib.parse import urlparse
from typing import Any

import plotly.graph_objects as go
import streamlit as st

SENTIMENTS = ("positive", "negative", "neutral", "mixed")
PALETTE = {
    "positive": "#26c992", "negative": "#fa5c80",
    "neutral": "#9a69f8", "mixed": "#409bfa",
}
SOURCE_LABELS = {"youtube": "YouTube", "hacker_news": "Hacker News"}
VIEWS = ("overview", "sentiment", "topics", "voice", "executive")


def clean(value: Any) -> str:
    return escape(str(value) if value is not None else "", quote=True)


def number(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def percent(value: Any) -> str:
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def navigate(view: str, *, focus: str | None = None) -> None:
    """Navigate without collecting or reprocessing source records."""
    if view not in VIEWS:
        raise ValueError(f"Unknown intelligence section: {view}")
    st.session_state.bp_phase = "dashboard"
    st.session_state.bp_dashboard_view = view
    if focus is not None and view == "sentiment":
        st.session_state.bp_sentiment_focus = focus
    st.rerun()


def _load_insights(*, force: bool = False) -> dict:
    brand = st.session_state.get("bp_brand", "")
    granularity = st.session_state.get("bp_trend_granularity", "month")
    cached = st.session_state.get("bp_dashboard_data")
    cached_brand = st.session_state.get("bp_dashboard_data_brand")
    cached_granularity = (cached or {}).get("metadata", {}).get("trend_granularity")
    if force or cached is None or cached_brand != brand or cached_granularity != granularity:
        from show_insights import show_insights
        cached = show_insights(
            brand_name=brand,
            topic_limit=20,
            feedback_limit=150,
            trend_granularity=granularity,
        )
        st.session_state.bp_dashboard_data = cached
        st.session_state.bp_dashboard_data_brand = brand
    return cached


def _header(title: str, eyebrow: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="bp-dash-hero"><div class="bp-eyebrow">{clean(eyebrow)}</div>'
        f'<h1 class="bp-page-title">{clean(title)}</h1>'
        f'<p class="bp-page-description">{clean(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def _kpi_cards(overview: dict) -> None:
    specs = [
        ("Total mentions", number(overview.get("total_mentions")), "◎", "blue", "Collected source records"),
        ("Relevant mentions", number(overview.get("relevant_mentions")), "◇", "mint", "Of analyzed mentions"),
        ("Positive sentiment", percent(overview.get("positive_percentage")), "☺", "mint", "Of relevant mentions"),
        ("Negative sentiment", percent(overview.get("negative_percentage")), "☹", "pink", "Of relevant mentions"),
        ("Unique topics", number(overview.get("total_topics")), "⬡", "violet", "Identified categories"),
    ]
    cards = []
    for label, value, icon, hue, caption in specs:
        cards.append(
            f'<div class="bp-dash-stat"><div class="bp-dash-stat-icon {hue}">{icon}</div>'
            f'<div class="bp-dash-stat-label">{clean(label)}</div>'
            f'<strong>{clean(value)}</strong><small>{clean(caption)}</small></div>'
        )
    st.markdown('<div class="bp-dash-stat-grid">' + ''.join(cards) + '</div>', unsafe_allow_html=True)


def _style_plot(fig: go.Figure, height: int = 280) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=12, r=12, t=14, b=16),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, Arial", color="#6b7a9c", size=12),
        hoverlabel=dict(bgcolor="#17204b", font_color="white"),
        legend=dict(orientation="h", y=1.13, x=0, font=dict(size=11)),
    )
    fig.update_xaxes(showgrid=False, showline=False, zeroline=False, tickfont=dict(color="#8d9bb6"))
    fig.update_yaxes(gridcolor="#edf1f9", zeroline=False, showline=False, tickfont=dict(color="#8d9bb6"))
    return fig


def _plot(fig: go.Figure, key: str) -> None:
    st.plotly_chart(fig, use_container_width=True, theme=None, key=key, config={"displayModeBar": False})


def _empty(message: str) -> None:
    st.info(message, icon="ℹ️")


def _donut(counts: dict, *, height: int = 285) -> go.Figure:
    values = [int(counts.get(s, 0) or 0) for s in SENTIMENTS]
    fig = go.Figure()
    if sum(values):
        fig.add_trace(go.Pie(
            labels=[s.title() for s in SENTIMENTS], values=values,
            hole=.70, sort=False,
            marker=dict(colors=[PALETTE[s] for s in SENTIMENTS], line=dict(color="white", width=3)),
            textinfo="none", hovertemplate="%{label}: %{value:,} (%{percent})<extra></extra>",
            showlegend=True,
        ))
        fig.add_annotation(text=f"<b>{number(sum(values))}</b><br><span style='font-size:11px'>Relevant</span>",
                           x=.5, y=.5, showarrow=False, font=dict(size=22, color="#14214f"))
    _style_plot(fig, height)
    fig.update_layout(legend=dict(orientation="v", x=1.02, y=.78, font=dict(size=11)),
                      margin=dict(l=0, r=15, t=5, b=5))
    return fig


def _trend(trend: list[dict], *, as_percent: bool, height: int = 280) -> go.Figure:
    fig = go.Figure()
    x = [p.get("period_start") for p in trend]
    for s in SENTIMENTS:
        y = [
            float(p.get("sentiment_percentages", {}).get(s, 0) or 0) if as_percent
            else int(p.get("sentiment_counts", {}).get(s, 0) or 0)
            for p in trend
        ]
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines+markers", name=s.title(),
            line=dict(color=PALETTE[s], width=3, shape="spline"),
            marker=dict(size=6),
            hovertemplate=f"%{{x}}<br>{s.title()}: %{{y:.1f}}{'%' if as_percent else ''}<extra></extra>",
        ))
    _style_plot(fig, height)
    if as_percent:
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
    return fig


def _sources(source_data: dict, height: int = 285) -> go.Figure:
    labels = ["YouTube", "Hacker News"]
    fig = go.Figure()
    for s in SENTIMENTS:
        y = [float(source_data.get(platform, {}).get("sentiment_percentages", {}).get(s, 0) or 0)
             for platform in ("youtube", "hacker_news")]
        fig.add_trace(go.Bar(
            x=labels, y=y, name=s.title(), marker_color=PALETTE[s],
            hovertemplate=f"%{{x}}<br>{s.title()}: %{{y:.1f}}%<extra></extra>",
        ))
    _style_plot(fig, height)
    fig.update_layout(barmode="group", bargap=.36, bargroupgap=.07)
    fig.update_yaxes(ticksuffix="%", range=[0, 100])
    return fig


def _topic_bar(topics: list[dict], height: int = 285) -> go.Figure:
    selected = list(reversed(topics[:8]))
    fig = go.Figure(go.Bar(
        x=[int(t.get("mention_count", 0) or 0) for t in selected],
        y=[t.get("topic", "Unknown") for t in selected],
        orientation="h", marker_color="#8064ef",
        hovertemplate="%{y}: %{x:,} mentions<extra></extra>",
        text=[number(t.get("mention_count")) for t in selected],
        textposition="outside", cliponaxis=False,
    ))
    _style_plot(fig, height)
    fig.update_layout(showlegend=False, margin=dict(l=6, r=43, t=10, b=15))
    fig.update_xaxes(showgrid=True, gridcolor="#f0f3fb", rangemode="tozero")
    return fig


def _topic_sentiments(topics: list[dict], height: int = 390) -> go.Figure:
    selected = list(reversed(topics[:12]))
    fig = go.Figure()
    names = [t.get("topic", "Unknown") for t in selected]
    for s in SENTIMENTS:
        vals = [float(t.get("sentiment_percentages", {}).get(s, 0) or 0) for t in selected]
        fig.add_trace(go.Bar(
            x=vals, y=names, orientation="h", name=s.title(), marker_color=PALETTE[s],
            hovertemplate=f"%{{y}}<br>{s.title()}: %{{x:.1f}}%<extra></extra>",
        ))
    _style_plot(fig, height)
    fig.update_layout(barmode="stack", bargap=.42)
    fig.update_xaxes(range=[0, 100], ticksuffix="%")
    return fig


def _card_title(title: str, label: str = "") -> None:
    st.markdown(f'<div class="bp-dash-panel-title">{clean(title)}'
                f'<span>{clean(label)}</span></div>', unsafe_allow_html=True)


def _card_html(title: str, body: str, tone: str = "violet") -> None:
    st.markdown(f'<div class="bp-dash-feature bp-dash-feature-{tone}">'
                f'<div class="bp-dash-feature-title">{clean(title)}</div>'
                f'<p>{clean(body)}</p></div>', unsafe_allow_html=True)


def _chart_card(title: str, fig: go.Figure, key: str, *, subtitle: str = "",
                cta: str | None = None, view: str = "sentiment", focus: str | None = None) -> None:
    with st.container(border=True):
        _card_title(title, subtitle)
        _plot(fig, key)
        if cta and st.button(cta, use_container_width=True, key=f"cta_{key}"):
            navigate(view, focus=focus)


def _coverage_notice(overview: dict, *, compact: bool = False) -> None:
    remaining = int(overview.get("pending_mentions", 0) or 0)
    analyzed = int(overview.get("analyzed_mentions", 0) or 0)
    collected = int(overview.get("total_mentions", 0) or 0)
    if remaining:
        st.info(f"Analysis coverage: {number(analyzed)} of {number(collected)} collected mentions have been analyzed; "
                f"{number(remaining)} remain pending. Sentiment and topic results cover analyzed relevant mentions only.")
    elif not compact:
        st.caption(f"Analyzed {number(analyzed)} of {number(collected)} collected mentions. "
                   "Percentages are based on relevant analyzed mentions, not all customers.")


def _format_excerpt(text: str, max_chars: int = 220) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= max_chars else text[:max_chars - 1].rstrip() + "…"


def _safe_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
        if parsed.scheme in ("https", "http") and parsed.hostname and parsed.hostname.lower() in (
            "youtube.com", "www.youtube.com", "youtu.be", "news.ycombinator.com"
        ):
            return url
    except (TypeError, ValueError):
        pass
    return None


def _feedback_card(entry: dict, *, sentiment: str, key: str) -> None:
    kind = entry.get("type") or "observation"
    topic = entry.get("topic") or "General"
    source = SOURCE_LABELS.get(entry.get("source"), entry.get("source") or "Source")
    product = entry.get("product_name")
    quote = entry.get("source_text")
    created = (entry.get("published_at") or "")[:10]
    with st.container(border=True):
        st.markdown(
            '<div class="bp-dash-feedback-head">'
            f'<span class="bp-dash-feedback-badge {clean(sentiment)}">{clean(topic)}</span>'
            f'<span class="bp-dash-feedback-kind">{clean(kind.replace("_", " ").title())}</span>'
            '</div>'
            f'<p class="bp-dash-feedback-text">{clean(entry.get("feedback") or "")}</p>',
            unsafe_allow_html=True,
        )
        if quote:
            st.caption(f"Source excerpt: “{_format_excerpt(quote)}”")
        details = f"{source} · {created or 'Date unavailable'}"
        if product:
            details += f" · {product}"
        st.caption(details)
        url = _safe_url(entry.get("url"))
        if url:
            st.link_button("↗ View original discussion", url=url, use_container_width=False)


def _overview(insights: dict) -> None:
    brand = insights.get("brand") or st.session_state.bp_brand
    overview = insights.get("overview") or {}
    trend = insights.get("sentiment_trend") or []
    _header("Brand Intelligence Overview", "BRAND INTELLIGENCE",
            f"Understand how {brand} is perceived across YouTube and Hacker News with evidence-backed AI insights.")
    _kpi_cards(overview)
    _coverage_notice(overview)
    left, mid, right = st.columns([1.12, .99, 1.05], gap="medium")
    with left:
        _chart_card("Sentiment Over Time", _trend(trend, as_percent=True, height=280),
                    "overview_trend", subtitle="Share by publication period",
                    cta="Explore sentiment trends  ↗", view="sentiment", focus="Trends")
    with mid:
        _chart_card("Sentiment Distribution", _donut(insights.get("sentiment_distribution") or {}, height=280),
                    "overview_donut", subtitle="Relevant analyzed mentions",
                    cta="Explore sentiment distribution  ↗", view="sentiment", focus="Distribution")
    with right:
        _chart_card("Source-wise Sentiment", _sources(insights.get("source_wise_sentiment") or {}, height=280),
                    "overview_sources", subtitle="Platform-specific percentages",
                    cta="Compare YouTube and Hacker News  ↗", view="sentiment", focus="Sources")
    a, b = st.columns([1.08, 1.45], gap="medium")
    with a:
        _chart_card("Top Discussed Topics", _topic_bar(insights.get("topic_intelligence") or [], height=315),
                    "overview_topics", subtitle="Mentions per topic · multiple per post",
                    cta="Explore topic intelligence  ↗", view="topics")
    with b:
        summary = insights.get("executive_summary") or {}
        _card_html("✧ AI Executive Summary", _format_excerpt(summary.get("executive_summary") or
                   "An executive summary hasn't been generated for this brand yet.", 750))
        if summary:
            st.caption(f"Saved summary · Generated {str(summary.get('generated_at') or 'at an unknown time')[:16]} "
                       f"· Based on {number(summary.get('relevant_mentions_count'))} relevant mentions")
        c1, c2 = st.columns(2, gap="small")
        with c1:
            _card_html("Positive Highlights", _format_excerpt(summary.get("positive_highlights") or
                        "No saved positive highlights available.", 240), "mint")
        with c2:
            _card_html("Negative Highlights", _format_excerpt(summary.get("negative_highlights") or
                        "No saved negative highlights available.", 240), "rose")
        if st.button("Read full executive insights  ↗", use_container_width=True, key="overview_executive"):
            navigate("executive")
    st.caption("BrandPulse AI analyzes collected public discussions; these are not representative customer surveys. "
               "The dashboard is read-only and does not rerun Ollama.")


def _sentiment(insights: dict) -> None:
    _header("Sentiment Intelligence", "DEEP DIVE / SENTIMENT",
            "Explore overall sentiment, differences between platforms, and publication-date trends.")
    overview = insights.get("overview") or {}
    _coverage_notice(overview, compact=True)
    focus = st.radio("Explore sentiment", ("Distribution", "Sources", "Trends"),
                     key="bp_sentiment_focus", horizontal=True)
    counts = insights.get("sentiment_distribution") or {}
    if focus == "Distribution":
        x, y = st.columns([1.2, 1], gap="medium")
        with x:
            _chart_card("Sentiment Distribution", _donut(counts, height=390), "sentiment_detail_donut",
                        subtitle="Four mutually exclusive sentiment categories")
        with y:
            with st.container(border=True):
                _card_title("Sentiment breakdown", "All relevant analyzed mentions")
                total = sum(int(counts.get(s, 0) or 0) for s in SENTIMENTS)
                for s in SENTIMENTS:
                    n = int(counts.get(s, 0) or 0)
                    frac = 100*n/total if total else 0
                    st.markdown(f'<div class="bp-dash-sent-row">'
                                f'<span><i style="background:{PALETTE[s]}"></i>{s.title()}</span>'
                                f'<b>{number(n)}</b><small>{frac:.1f}%</small></div>', unsafe_allow_html=True)
                st.caption("Mixed is separate; positive + negative + neutral + mixed = 100% before rounding.")
    elif focus == "Sources":
        _chart_card("Platform Sentiment Comparison", _sources(insights.get("source_wise_sentiment") or {}, 410),
                    "sentiment_detail_sources", subtitle="Within-platform percentages · not raw volume")
        c1, c2 = st.columns(2, gap="medium")
        for col, source in zip((c1, c2), ("youtube", "hacker_news")):
            d = (insights.get("source_wise_sentiment") or {}).get(source) or {}
            with col:
                with st.container(border=True):
                    _card_title(SOURCE_LABELS[source], "Relevant analyzed mentions")
                    st.metric("Mentions", number(d.get("total_mentions")))
                    st.caption(" · ".join(f"{s.title()} {percent((d.get('sentiment_percentages') or {}).get(s))}" for s in SENTIMENTS))
    else:
        granularity = st.session_state.get("bp_trend_granularity", "month")
        st.caption(f"Trends use original publication dates, grouped by {granularity}. "
                   "Source records without a publication date are excluded from the timeline.")
        as_pct = st.radio("Display", ["Sentiment share (%)", "Mention counts"], horizontal=True,
                          key="bp_trend_display") == "Sentiment share (%)"
        _chart_card("Sentiment Over Time", _trend(insights.get("sentiment_trend") or [], as_percent=as_pct, height=425),
                    "sentiment_detail_trend", subtitle=f"{granularity.title()}ly periods")
    if st.button("← Return to Overview", key="sentiment_back"):
        navigate("overview")


def _topics(insights: dict) -> None:
    _header("Topic Intelligence", "DEEP DIVE / TOPICS",
            "Discover which brand aspects attract discussion and understand the sentiment toward each one.")
    topics = insights.get("topic_intelligence") or []
    if not topics:
        _empty("No topic insights have been saved for the selected brand yet.")
        return
    _chart_card("Topic-wise Sentiment", _topic_sentiments(topics, height=max(390, 36 * min(len(topics), 12))),
                "topics_stacked", subtitle="Positive · Negative · Neutral · Mixed, within each topic")
    st.caption("A mention can discuss multiple topics; the total number of topic associations can exceed relevant mentions.")
    left, right = st.columns([1.2, 1], gap="medium")
    with left:
        with st.container(border=True):
            _card_title("Most Discussed Topics", "Count and sentiment breakdown")
            for t in topics:
                tname = t.get("topic") or "Other"
                cnt = int(t.get("mention_count", 0) or 0)
                portions = t.get("sentiment_percentages") or {}
                sections = ''.join(f'<i style="width:{max(0, float(portions.get(s,0) or 0)):.2f}%;background:{PALETTE[s]}"></i>' for s in SENTIMENTS)
                st.markdown(f'<div class="bp-dash-topic-row"><div><b>{clean(tname)}</b><span>{number(cnt)} mentions</span></div>'
                            f'<div class="bp-dash-split">{sections}</div></div>', unsafe_allow_html=True)
    with right:
        names = [t.get("topic") for t in topics]
        selection = st.selectbox("Inspect a topic", names, key="bp_selected_topic")
        selected = next((t for t in topics if t.get("topic") == selection), {})
        counts = selected.get("sentiment_counts") or {}
        with st.container(border=True):
            _card_title(f"{selection} — details", "Topic-level sentiment")
            st.metric("Mentions discussing this topic", number(selected.get("mention_count")))
            for s in SENTIMENTS:
                pct = (selected.get("sentiment_percentages") or {}).get(s, 0)
                st.caption(f"{s.title()}: {number(counts.get(s))} mentions · {percent(pct)}")
        positives = [x for x in insights.get("positive_feedback") or [] if (x.get("topic") or "").casefold() == (selection or "").casefold()]
        negatives = [x for x in insights.get("negative_feedback") or [] if (x.get("topic") or "").casefold() == (selection or "").casefold()]
        st.caption("Examples below come from the latest retrieved feedback sample, not all historical comments.")
        for s, records in (("positive", positives[:2]), ("negative", negatives[:2])):
            for i, record in enumerate(records):
                _feedback_card(record, sentiment=s, key=f"topic_{s}_{i}")
        if st.button("Explore all feedback  ↗", use_container_width=True, key="topics_to_voice"):
            navigate("voice")
    if st.button("← Return to Overview", key="topics_back"):
        navigate("overview")


def _voice(insights: dict) -> None:
    _header("Customer Voice", "DEEP DIVE / FEEDBACK",
            "Investigate positive experiences and complaints, each connected to its original source discussion.")
    kind = st.radio("Feedback type", ["Positive", "Negative"], horizontal=True, key="bp_voice_kind")
    polarity = kind.lower()
    feedback = insights.get("positive_feedback" if polarity == "positive" else "negative_feedback") or []
    st.caption(f"Showing up to {number(insights.get('metadata',{}).get('feedback_limit',150))} most recently published "
               f"{polarity} feedback observations. These are excerpts, not deduplicated customer counts.")
    if not feedback:
        _empty(f"No {polarity} feedback observations have been saved in the loaded sample.")
        return
    col_a, col_b = st.columns(2, gap="medium")
    with col_a:
        sources = sorted({x.get("source") for x in feedback if x.get("source")})
        source = st.selectbox("Source", ["All sources"] + sources, key=f"bp_voice_source_{polarity}")
    with col_b:
        tags = sorted({x.get("topic") for x in feedback if x.get("topic")})
        topic = st.selectbox("Topic", ["All topics"] + tags, key=f"bp_voice_topic_{polarity}")
    filtered = [entry for entry in feedback if
                (source == "All sources" or entry.get("source") == source) and
                (topic == "All topics" or entry.get("topic") == topic)]
    st.caption(f"{number(len(filtered))} observations matching filters (within the loaded sample).")
    if not filtered:
        _empty("No feedback observations match the selected filters.")
        return
    cols = st.columns(2, gap="medium")
    for idx, entry in enumerate(filtered[:24]):
        with cols[idx % 2]:
            _feedback_card(entry, sentiment=polarity, key=f"voice_{idx}")
    if len(filtered) > 24:
        st.info("Showing the first 24 filtered observations. Narrow the topic or source to inspect more.")


def _executive(insights: dict) -> None:
    _header("Executive Insights", "AI INTELLIGENCE / EXECUTIVE SUMMARY",
            "A business-oriented synthesis of saved brand feedback, with the supporting analysis context.")
    summary = insights.get("executive_summary")
    if not summary:
        _empty("No saved executive summary exists yet. Process all pending mentions and generate the initial summary first.")
        return
    overview = insights.get("overview") or {}
    analyzed_at_summary = summary.get("relevant_mentions_count")
    current = overview.get("relevant_mentions")
    st.caption(f"Saved on {str(summary.get('generated_at') or 'unknown date')[:19]} · "
               f"Based on {number(analyzed_at_summary)} relevant mentions · "
               f"Model: {summary.get('model_name') or 'unknown'}")
    if current is not None and analyzed_at_summary is not None and int(current) != int(analyzed_at_summary):
        st.info("This Phase 1 executive summary was generated from an earlier set of analyzed mentions. "
                "The charts and KPI counts reflect the currently stored analysis; summary refresh is deferred to Phase 2.")
    _card_html("✧ Executive Brand Summary", summary.get("executive_summary") or "No summary text available.")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        _card_html("Positive Highlights", summary.get("positive_highlights") or "No positive highlights available.", "mint")
        _card_html("Demonstrated Strengths", summary.get("strengths_summary") or "No strengths summary available.", "blue")
    with c2:
        _card_html("Negative Highlights", summary.get("negative_highlights") or "No negative highlights available.", "rose")
        with st.container(border=True):
            _card_title("How to interpret these findings")
            st.write("These are AI-generated syntheses of sampled public conversations, not verified facts about every customer. "
                     "Use original source discussions to validate important complaints and strengths.")
    if st.button("Explore customer evidence  ↗", use_container_width=True, key="executive_voice"):
        navigate("voice")


def render_intelligence_workspace() -> None:
    """Entrypoint called from app.py for the dashboard phase."""
    controls = st.columns([1.35, 1, 1, 1], gap="small", vertical_alignment="bottom")
    with controls[0]:
        st.markdown('<div class="bp-dash-eyebrow">✧ &nbsp; SAVED BRAND INTELLIGENCE</div>', unsafe_allow_html=True)
    with controls[1]:
        st.selectbox("Trend grouping", ["month", "week"], key="bp_trend_granularity",
                     format_func=lambda x: "Monthly" if x == "month" else "Weekly")
    with controls[2]:
        if st.button("↻ Refresh saved insights", use_container_width=True, key="refresh_insights"):
            st.session_state.bp_dashboard_data = None
            st.rerun()
    with controls[3]:
        if st.button("← AI processing result", use_container_width=True, key="back_to_ai_result"):
            st.session_state.bp_phase = "analyzed"
            st.rerun()
    try:
        insights = _load_insights()
    except Exception as exc:
        st.error(f"Unable to load saved brand intelligence: {type(exc).__name__}: {exc}")
        st.info("Check that show_insights.py and your SQL Server connection are working, then select Refresh saved insights.")
        return
    view = st.session_state.get("bp_dashboard_view", "overview")
    if view == "overview":
        _overview(insights)
    elif view == "sentiment":
        _sentiment(insights)
    elif view == "topics":
        _topics(insights)
    elif view == "voice":
        _voice(insights)
    elif view == "executive":
        _executive(insights)
    else:
        st.session_state.bp_dashboard_view = "overview"
        _overview(insights)
