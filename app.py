"""BrandPulse Aurora — ingestion and AI processing workflow.

Five UI states: home, fetching, collected, analyzing, analyzed; plus an error state.
Backend progress is streamed synchronously through Python callbacks.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st

from ingest import ingest_brand  # Reuse your working ingestion module, unchanged.


st.set_page_config(
    page_title="BrandPulse AI | Brand Intelligence",
    page_icon="💠",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS_PATH = Path(__file__).with_name("aurora.css")
st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

STAGES = ("database", "youtube", "hacker_news", "storage")
AI_STAGES = ("database", "loading", "records", "summary")
AI_STAGE_LABELS = {
    "database": "Preparing database",
    "loading": "Finding pending mentions",
    "records": "Analyzing brand mentions",
    "summary": "Executive summary",
    "completed": "AI processing complete",
}
STAGE_LABELS = {
    "database": "Database initialization",
    "youtube": "YouTube collection",
    "hacker_news": "Hacker News collection",
    "storage": "Deduplicate & save",
}


def h(value: Any) -> str:
    return escape(str(value) if value is not None else "", quote=True)


def nice_num(value: Any, *, unknown: bool = False) -> str:
    if unknown and value is None:
        return "—"
    try:
        return f"{int(value or 0):,}"
    except (TypeError, ValueError):
        return "—"


def initialize_state() -> None:
    defaults = {
        "bp_phase": "home",  # home | fetching | collected | error
        "bp_brand": "",
        "bp_events": [],
        "bp_stages": {},
        "bp_metrics": {},
        "bp_summary": None,
        "bp_error": "",
        "bp_run_pending": False,
        "bp_ai_run_pending": False,
        "bp_ai_events": [],
        "bp_ai_stages": {},
        "bp_ai_metrics": {},
        "bp_ai_result": None,
        "bp_error_origin": "ingestion",
        "bp_ai_max_records": 100,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def reset_home() -> None:
    st.session_state.bp_phase = "home"
    st.session_state.bp_brand = ""
    st.session_state.bp_events = []
    st.session_state.bp_stages = {}
    st.session_state.bp_metrics = {}
    st.session_state.bp_summary = None
    st.session_state.bp_error = ""
    st.session_state.bp_run_pending = False
    st.session_state.bp_ai_run_pending = False
    st.session_state.bp_ai_events = []
    st.session_state.bp_ai_stages = {}
    st.session_state.bp_ai_metrics = {}
    st.session_state.bp_ai_result = None
    st.session_state.bp_error_origin = "ingestion"


def start_collection(brand: str) -> None:
    st.session_state.bp_brand = brand.strip()
    st.session_state.bp_phase = "fetching"
    st.session_state.bp_events = []
    st.session_state.bp_stages = {}
    st.session_state.bp_metrics = {}
    st.session_state.bp_summary = None
    st.session_state.bp_error = ""
    st.session_state.bp_run_pending = True
    st.session_state.bp_ai_run_pending = False
    st.session_state.bp_ai_events = []
    st.session_state.bp_ai_stages = {}
    st.session_state.bp_ai_metrics = {}
    st.session_state.bp_ai_result = None
    st.session_state.bp_error_origin = "ingestion"


def start_ai_analysis() -> None:
    """Switch to the actual AI runner; no backend work in button handler."""
    st.session_state.bp_phase = "analyzing"
    st.session_state.bp_ai_run_pending = True
    st.session_state.bp_ai_events = []
    st.session_state.bp_ai_stages = {}
    st.session_state.bp_ai_metrics = {}
    st.session_state.bp_ai_result = None
    st.session_state.bp_error = ""
    st.session_state.bp_error_origin = "analysis"


def logo_html() -> str:
    return """
    <div class="bp-logo">
      <svg class="bp-logo-wave" viewBox="0 0 48 46" aria-hidden="true">
        <defs><linearGradient id="bp-wave-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#13c4f7"/>
          <stop offset="55%" stop-color="#5279ff"/>
          <stop offset="100%" stop-color="#a43aff"/>
        </linearGradient></defs>
        <path d="M1 23 H8 L12 9 L17 38 L23 2 L29 44 L35 15 L39 23 H47"
        fill="none" stroke="url(#bp-wave-grad)" stroke-width="3.5"
        stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <div class="bp-logo-word">BrandPulse<span>AI</span></div>
    </div>
    """


def sidebar() -> None:
    with st.sidebar:
        st.markdown(logo_html(), unsafe_allow_html=True)
        phase = st.session_state.bp_phase
        home_class = "bp-nav-active" if phase == "home" else ""
        collection_class = "bp-nav-active" if phase in ("fetching", "collected") else ""
        analysis_class = "bp-nav-active" if phase in ("analyzing", "analyzed") else ""
        items = [
            ("⌂", "Home", home_class, ""),
            ("◉", "Collection", collection_class, ""),
            ("✦", "AI Processing", analysis_class, ""),
            ("▥", "Overview", "bp-nav-soon", "Soon"),
            ("◔", "Sentiment", "bp-nav-soon", "Soon"),
            ("⬡", "Topics", "bp-nav-soon", "Soon"),
            ("☰", "Customer Voice", "bp-nav-soon", "Soon"),
            ("✦", "Executive Insights", "bp-nav-soon", "Soon"),
        ]
        entries = "".join(
            f'<div class="bp-nav-row {cls}"><span class="bp-nav-ico">{ico}</span>'
            f'<span>{h(name)}</span><small>{h(tag)}</small></div>'
            for ico, name, cls, tag in items
        )
        st.markdown(f'<nav class="bp-nav">{entries}</nav>', unsafe_allow_html=True)
        st.markdown(
            '<div class="bp-sidebar-footer">'
            '<span class="bp-footer-dot"></span> BrandPulse Aurora'
            '<div>Collection + AI processing</div></div>',
            unsafe_allow_html=True,
        )
        if phase not in ("home", "fetching", "analyzing"):
            if st.button("← Back to Home", use_container_width=True, key="nav_home"):
                reset_home()
                st.rerun()


def topbar() -> None:
    phase = st.session_state.bp_phase
    brand = st.session_state.bp_brand
    status = {
        "home": "AI-powered brand intelligence",
        "fetching": "Collecting live mentions",
        "collected": "Mentions collected",
        "analyzing": "AI processing in progress",
        "analyzed": "AI processing run complete",
        "error": "Action needed",
    }.get(phase, "Brand intelligence")
    brand_pill = f'<span class="bp-brand-pill">◈ {h(brand)}</span>' if brand else ""
    st.markdown(
        '<div class="bp-topbar">'
        '<div class="bp-topbar-tag">◉ &nbsp; Explore conversations. Understand perception.</div>'
        f'<div class="bp-topbar-right">{brand_pill}'
        f'<span class="bp-topbar-status"><i></i>{h(status)}</span></div></div>',
        unsafe_allow_html=True,
    )


def preview_html() -> str:
    heights = [33, 51, 44, 60, 38, 53, 42, 71, 57, 66, 47, 79, 53, 61, 87]
    bars = "".join(
        f'<span class="bp-preview-bar" style="height:{height}%"></span>'
        for height in heights
    )
    kpis = [
        ("Total mentions", "3.4k", "#4b9dff", "◉"),
        ("Positive sentiment", "62%", "#26c994", "☺"),
        ("Negative sentiment", "18%", "#fd648a", "☹"),
        ("Unique topics", "28", "#a55cff", "✧"),
    ]
    mini = "".join(
        f'<div class="bp-preview-kpi"><div class="bp-preview-kpi-label">'
        f'<span style="color:{color}">{icon}</span> {h(label)}</div>'
        f'<strong>{value}</strong><span class="bp-preview-mini-line"></span></div>'
        for label, value, color, icon in kpis
    )
    topics = [("AI Features", 83), ("Pricing", 64), ("Performance", 47), ("Customer Support", 28)]
    topic_html = "".join(
        f'<div class="bp-preview-topic"><span>{h(label)}</span>'
        f'<div class="bp-mini-track"><div style="width:{width}%"></div></div></div>'
        for label, width in topics
    )
    return f"""
      <div class="bp-preview-aura"><div class="bp-preview-card">
        <div class="bp-preview-head"><span>✧ BrandPulse AI</span>
          <span class="bp-preview-sample">SAMPLE PREVIEW</span></div>
        <div class="bp-preview-kpis">{mini}</div>
        <div class="bp-preview-panels">
          <div class="bp-preview-panel"><div class="bp-preview-title">Mentions over time</div>
          <div class="bp-preview-chart">{bars}</div>
          <div class="bp-preview-x">APR 01 <span>APR 15</span> APR 30</div></div>
          <div class="bp-preview-panel"><div class="bp-preview-title">Top discussion topics</div>
          {topic_html}</div>
        </div>
        <div class="bp-preview-caption">Illustrative dashboard · Not live brand data</div>
      </div></div>
    """


def how_it_works() -> None:
    steps = [
        ("01", "⌕", "Fetch mentions", "Discover conversations on YouTube and Hacker News.", "cyan"),
        ("02", "▤", "Filter & organize", "Store source records and skip existing mentions.", "blue"),
        ("03", "✧", "AI analysis", "Identify relevance, sentiment, topics, and feedback.", "violet"),
        ("04", "▥", "Explore insights", "Understand trends, strengths, and key complaints.", "mint"),
    ]
    cards = "".join(
        f'<div class="bp-how-card"><div class="bp-how-head"><span class="bp-how-icon {theme}">{icon}</span>'
        f'<span class="bp-step-number">{num}</span></div><strong>{h(title)}</strong>'
        f'<p>{h(description)}</p></div>'
        for num, icon, title, description, theme in steps
    )
    st.markdown(
        '<section class="bp-how"><div class="bp-eyebrow">A SIMPLE FOUR-STEP PROCESS</div>'
        '<div class="bp-how-title-row"><h2>How It Works</h2>'
        '<p>From public conversations to meaningful brand intelligence.</p></div>'
        f'<div class="bp-how-grid">{cards}</div></section>',
        unsafe_allow_html=True,
    )


def home_page() -> None:
    left, right = st.columns([1.02, 1.05], gap="large", vertical_alignment="center")
    with left:
        st.markdown(
            '<div class="bp-eyebrow bp-home-eyebrow">AI-POWERED BRAND INTELLIGENCE</div>'
            '<h1 class="bp-hero-title">Turn online mentions<br>into '
            '<span>brand intelligence</span></h1>'
            '<p class="bp-hero-description">Analyze YouTube and Hacker News '
            'conversations with AI to understand how people perceive your brand.</p>',
            unsafe_allow_html=True,
        )
        with st.form("bp_brand_form", clear_on_submit=False):
            brand = st.text_input(
                "Enter your brand or company name",
                placeholder="e.g. Microsoft",
                key="bp_brand_input",
                max_chars=150,
            )
            submitted = st.form_submit_button(
                "✦  Fetch Brand Mentions   →",
                type="primary",
                use_container_width=True,
            )
        st.markdown(
            '<div class="bp-source-note"><span class="bp-source-yt">▶</span>'
            '<span class="bp-note-plus">+</span><span class="bp-source-hn">Y</span>'
            '<span class="bp-note-plus">+</span><span class="bp-source-ai">✧</span>'
            ' YouTube + Hacker News + AI intelligence</div>',
            unsafe_allow_html=True,
        )
        if submitted:
            if not brand.strip():
                st.error("Enter a brand or company name to start collecting mentions.")
            else:
                start_collection(brand)
                st.rerun()
    with right:
        st.markdown(preview_html(), unsafe_allow_html=True)
    how_it_works()


def stage_overview(stages: dict[str, str]) -> str:
    # Four practical phases of ingestion. This reports discrete stage completion,
    # NOT wall-clock progress or expected remaining time.
    completed = sum(stages.get(stage) == "completed" for stage in STAGES)
    pct = 25 * completed
    active = next((stage for stage in STAGES if stages.get(stage) in ("started", "running")), None)
    if active is None and completed < 4:
        active = next((stage for stage in STAGES if stages.get(stage) != "completed"), None)
    active_label = STAGE_LABELS.get(active, "Finishing collection")
    return f"""
    <div class="bp-progress-main">
      <div class="bp-panel-top"><span class="bp-panel-title">⚡ &nbsp; Data Collection Progress</span>
      <span class="bp-live-chip"><i></i> LIVE</span></div>
      <div class="bp-progress-inner">
        <div class="bp-progress-ring" style="--bp-progress:{pct}%">
          <div class="bp-progress-ring-inside"><strong>{pct}%</strong>
          <small>Stages complete</small></div></div>
        <div class="bp-progress-info"><div class="bp-progress-status">{h(active_label)}</div>
          <p>Collecting and preparing brand mentions for SQL Server.</p>
          <div class="bp-progress-count">{completed} of 4 ingestion stages completed</div>
          <div class="bp-progress-caption">Milestone completion, not estimated time remaining</div>
        </div></div>
    </div>
    """


def progress_stepper(stages: dict[str, str]) -> str:
    fetched = stages.get("youtube") == "completed" and stages.get("hacker_news") == "completed"
    stored = stages.get("storage") == "completed"
    labels = ["Fetch mentions", "Filter & organize", "AI analysis", "Explore insights"]
    desc = ["YouTube + Hacker News", "Save & deduplicate", "Next phase", "Coming soon"]
    status = ["done" if fetched else "active", "done" if stored else "active" if fetched else "pending", "pending", "pending"]
    steps = "".join(
        f'<div class="bp-step bp-step-{st}"><span class="bp-step-circle">'
        f'{"✓" if st == "done" else index}</span><div><strong>{h(label)}</strong>'
        f'<small>{h(desc[index-1])}</small></div></div>'
        for index, (label, st) in enumerate(zip(labels, status), start=1)
    )
    return f'<div class="bp-stepper">{steps}</div>'


def metric_tile(title: str, value: str, symbol: str, cls: str, note: str = "") -> str:
    return (f'<div class="bp-metric-tile"><span class="bp-metric-icon {cls}">{symbol}</span>'
            f'<div><small>{h(title)}</small><strong>{h(value)}</strong>'
            f'<span class="bp-metric-note">{h(note)}</span></div></div>')


def progress_metrics(metrics: dict[str, Any], stages: dict[str, str]) -> str:
    yt = metrics.get("youtube_comments_fetched", metrics.get("comments_fetched"))
    hn = metrics.get("hacker_news_items_fetched", metrics.get("items_prepared", metrics.get("items_fetched")))
    storage_done = stages.get("storage") == "completed"
    new = metrics.get("new_raw_mentions") if storage_done else None
    old = metrics.get("existing_raw_mentions") if storage_done else None
    yt_note = "Collected so far" if yt is not None else "Awaiting source"
    hn_note = "Collected so far" if hn is not None else "Awaiting source"
    tiles = [
        metric_tile("YouTube comments", nice_num(yt, unknown=True), "▶", "yt", yt_note),
        metric_tile("Hacker News items", nice_num(hn, unknown=True), "Y", "hn", hn_note),
        metric_tile("New raw mentions", nice_num(new, unknown=True), "✧", "new", "Known after storage" if not storage_done else "New database records"),
        metric_tile("Existing raw mentions", nice_num(old, unknown=True), "▤", "old", "Known after storage" if not storage_done else "Skipped existing IDs"),
    ]
    video_p = metrics.get("videos_processed")
    video_n = metrics.get("videos_total")
    video_note = (f'<div class="bp-video-note">YouTube video coverage: '
                  f'{nice_num(video_p)} / {nice_num(video_n)} videos processed</div>') if video_n else ""
    return f'<div class="bp-metrics-grid">{"".join(tiles)}</div>{video_note}'


def event_time(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%H:%M:%S UTC")
    except ValueError:
        return ""


def activity_feed(events: list[dict[str, Any]], is_running: bool, failed: bool = False) -> str:
    """Render events as history; animate only the newest active event."""
    displayed = events[-9:]
    entries = []

    for index, event in enumerate(displayed):
        state = event.get("status", "running")
        is_latest = index == len(displayed) - 1

        if state == "completed":
            class_name, marker = "ok", "✓"
        elif state == "failed":
            class_name, marker = "bad", "!"
        elif is_running and is_latest and state in ("started", "running"):
            # Only the current event should look active and animate.
            class_name, marker = "live", "◌"
        else:
            # Earlier start/running notifications are historical events.
            # Keep them neutral; never imply they are still running.
            class_name, marker = "past", "•"

        msg = h(event.get("message", "Updating..."))
        stage_name = h(STAGE_LABELS.get(event.get("stage"), event.get("stage", "Activity")))
        entries.append(
            f'<div class="bp-feed-row"><span class="bp-feed-marker {class_name}">{marker}</span>'
            f'<div class="bp-feed-content"><strong>{msg}</strong><small>{stage_name}</small></div>'
            f'<time>{h(event_time(event.get("timestamp")))}</time></div>'
        )

    if not entries:
        entries.append('<div class="bp-feed-empty">Waiting for the first backend event…</div>')

    pill = (
        '<span class="bp-feed-error-pill">Interrupted</span>' if failed
        else '<span class="bp-live-chip"><i></i> LIVE</span>' if is_running
        else '<span class="bp-finished-chip">Complete</span>'
    )
    return (
        '<div class="bp-activity-card"><div class="bp-panel-top"><span class="bp-panel-title">'
        '☷ &nbsp; Live Activity Feed</span>' + pill + '</div><div class="bp-feed-list">'
        + "".join(entries) + '</div></div>'
    )


def sources_strip(stages: dict[str, str], metrics: dict[str, Any]) -> str:
    def source_box(label: str, stage: str, logo: str, cls: str, count: Any) -> str:
        status = stages.get(stage, "pending")
        status_text = "Complete" if status == "completed" else "Collecting" if status in ("running", "started") else "Pending"
        return (f'<div class="bp-source-card"><span class="bp-source-logo {cls}">{logo}</span>'
                f'<div><strong>{label}</strong><small>{h(status_text)}</small></div>'
                f'<b>{nice_num(count, unknown=True)}</b></div>')
    yt = metrics.get("youtube_comments_fetched", metrics.get("comments_fetched"))
    hn = metrics.get("hacker_news_items_fetched", metrics.get("items_prepared", metrics.get("items_fetched")))
    return f'<div class="bp-sources-grid">{source_box("YouTube", "youtube", "▶", "yt", yt)}{source_box("Hacker News", "hacker_news", "Y", "hn", hn)}</div>'


def section_heading(brand: str) -> None:
    st.markdown(
        f'<div class="bp-selected-brand">◈ &nbsp; {h(brand)}</div>'
        '<div class="bp-eyebrow">LIVE DATA INGESTION</div>'
        '<h1 class="bp-page-title">Fetching <span>Brand Mentions</span></h1>'
        f'<p class="bp-page-description">Collecting YouTube and Hacker News discussions '
        f'about <strong>{h(brand)}</strong>. Live progress appears below.</p>',
        unsafe_allow_html=True,
    )


def render_collection_screen(run: bool) -> None:
    brand = st.session_state.bp_brand
    section_heading(brand)
    stepper = st.empty()
    left, right = st.columns([1.52, 1], gap="large", vertical_alignment="top")
    with left:
        ring_placeholder = st.empty()
        metrics_placeholder = st.empty()
        sources_placeholder = st.empty()
    with right:
        activity_placeholder = st.empty()
    info_placeholder = st.empty()

    def render_all() -> None:
        stages = st.session_state.bp_stages
        metrics = st.session_state.bp_metrics
        events = st.session_state.bp_events
        stepper.markdown(progress_stepper(stages), unsafe_allow_html=True)
        ring_placeholder.markdown(stage_overview(stages), unsafe_allow_html=True)
        metrics_placeholder.markdown(progress_metrics(metrics, stages), unsafe_allow_html=True)
        sources_placeholder.markdown(sources_strip(stages, metrics), unsafe_allow_html=True)
        activity_placeholder.markdown(activity_feed(events, True), unsafe_allow_html=True)
        info_placeholder.markdown(
            '<div class="bp-inline-notice">ⓘ &nbsp; Raw fetched mentions may include '
            'existing database records. New/duplicate counts appear after SQL storage '
            'completes. AI analysis begins separately in the next phase.</div>',
            unsafe_allow_html=True,
        )

    render_all()

    if not run:
        st.warning("Collection was interrupted. Return home and start a new collection attempt.")
        if st.button("Return Home", key="interrupted_back"):
            reset_home()
            st.rerun()
        return

    # Run only once for a form submission. The synchronous callback updates the
    # live Streamlit placeholders without rerunning the whole script.
    st.session_state.bp_run_pending = False

    def on_progress(event: dict[str, Any]) -> None:
        st.session_state.bp_events.append(event)
        st.session_state.bp_events = st.session_state.bp_events[-60:]
        stage = event.get("stage")
        status = event.get("status")
        if stage in STAGES and status in ("started", "running", "completed", "failed"):
            st.session_state.bp_stages[stage] = status
        received_metrics = event.get("metrics") or {}
        if isinstance(received_metrics, dict):
            st.session_state.bp_metrics.update(received_metrics)
        render_all()

    try:
        result = ingest_brand(brand_name=brand, progress_callback=on_progress)
    except Exception as exc:
        st.session_state.bp_error = f"{type(exc).__name__}: {exc}"
        st.session_state.bp_phase = "error"
    else:
        st.session_state.bp_summary = result
        st.session_state.bp_phase = "collected"
    st.rerun()


# =============================================================
# COLLECTION COMPLETE — a separate page, not the progress page
# =============================================================
def collection_result_values() -> tuple[int | None, int | None, int | None, int, int]:
    m = st.session_state.bp_metrics
    yt = m.get("youtube_comments_fetched", m.get("comments_fetched"))
    hn = m.get("hacker_news_items_fetched", m.get("items_prepared", m.get("items_fetched")))
    total = m.get("total_mentions_fetched")
    if total is None and yt is not None and hn is not None:
        total = int(yt) + int(hn)
    return total, m.get("new_raw_mentions"), m.get("existing_raw_mentions"), int(yt or 0), int(hn or 0)


def collection_charts(total: int | None, new: int | None, existing: int | None, yt: int, hn: int) -> str:
    n = yt + hn
    pct = yt / n * 100 if n else 0
    pct_hn = 100 - pct if n else 0
    donut = f'conic-gradient(#fa4c61 0 {pct:.2f}%, #ff982b {pct:.2f}% 100%)' if n else '#edf1fb'
    denom = new + existing if new is not None and existing is not None else 0
    pct_new = new / denom * 100 if denom else 0
    pct_existing = existing / denom * 100 if denom else 0
    return f'''
      <div class="bp-charts-two">
        <div class="bp-chart-card">
          <div class="bp-chart-heading">Mentions by Source</div>
          <div class="bp-donut-flex">
            <div class="bp-donut" style="background:{donut}"><div class="bp-donut-center">
              <strong>{nice_num(n)}</strong><small>Fetched mentions</small></div></div>
            <div class="bp-chart-legend">
              <div><span class="bp-legend-dot bp-ytdot"></span>YouTube <b>{nice_num(yt)}</b><small>{pct:.1f}%</small></div>
              <div><span class="bp-legend-dot bp-hndot"></span>Hacker News <b>{nice_num(hn)}</b><small>{pct_hn:.1f}%</small></div>
            </div>
          </div>
        </div>
        <div class="bp-chart-card">
          <div class="bp-chart-heading">New vs Existing Raw Records</div>
          <div class="bp-compare-bars">
            <div class="bp-bar-group"><strong>{nice_num(new, unknown=True)}</strong>
              <div class="bp-bar-track"><div class="bp-bar-fill bp-bar-green" style="height:{pct_new:.2f}%"></div></div>
              <small>New</small></div>
            <div class="bp-bar-group"><strong>{nice_num(existing, unknown=True)}</strong>
              <div class="bp-bar-track"><div class="bp-bar-fill bp-bar-purple" style="height:{pct_existing:.2f}%"></div></div>
              <small>Already stored</small></div>
          </div>
          <p class="bp-data-caption">Counts reflect raw source IDs in this ingestion run, not AI relevance.</p>
        </div>
      </div>'''


def collected_page() -> None:
    brand = st.session_state.bp_brand
    metrics = st.session_state.bp_metrics
    total, new, existing, yt, hn = collection_result_values()
    initial = h(brand[:1].upper() or "B")
    st.markdown(
        '<div class="bp-finish-hero"><div class="bp-finish-intro">'
        '<div class="bp-eyebrow">DATA INGESTION COMPLETED</div>'
        '<h1 class="bp-page-title">Mentions Collected<br><span>Successfully</span></h1>'
        f'<p class="bp-page-description">YouTube and Hacker News mentions for <strong>{h(brand)}</strong> '
        'have been fetched, deduplicated, and saved in SQL Server.</p></div>'
        f'<div class="bp-brand-context"><span class="bp-brand-avatar">{initial}</span>'
        f'<div><small>SELECTED BRAND</small><strong>{h(brand)}</strong>'
        f'<p>{nice_num(total, unknown=True)} mentions fetched this run</p></div></div></div>'
        '<div class="bp-success-banner">✓ &nbsp; Data fetching and duplicate filtering completed successfully.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="bp-complete-cards bp-five-cards">'
        + metric_tile("Total fetched", nice_num(total, unknown=True), "◎", "new", "This collection run")
        + metric_tile("New raw mentions", nice_num(new, unknown=True), "✧", "mint", "Inserted into SQL Server")
        + metric_tile("Already stored", nice_num(existing, unknown=True), "▤", "old", "Existing source IDs")
        + metric_tile("YouTube comments", nice_num(yt), "▶", "yt", "Fetched this run")
        + metric_tile("Hacker News", nice_num(hn), "Y", "hn", "Fetched this run")
        + '</div>', unsafe_allow_html=True,
    )
    chart_col, next_col = st.columns([1.55, 1], gap="large", vertical_alignment="top")
    with chart_col:
        st.markdown(collection_charts(total, new, existing, yt, hn), unsafe_allow_html=True)
    with next_col:
        st.markdown(
            '<div class="bp-next-card bp-action-next"><div class="bp-next-kicker">✧ NEXT STEP</div>'
            '<h3>Ready for AI Intelligence</h3>'
            '<p>Analyze all brand-associated mentions that still need AI insights, '
            'including records already stored in the database. Discover sentiment, '
            'topics, strengths, and complaints.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("✧  Process AI Insights   →", type="primary", use_container_width=True, key="go_ai"):
            start_ai_analysis()
            st.rerun()
        if st.button("← Analyze another brand", use_container_width=True, key="another_brand_collected"):
            reset_home()
            st.rerun()
    with st.expander("View collection activity history", expanded=False):
        st.markdown(activity_feed(st.session_state.bp_events, False), unsafe_allow_html=True)


# =============================================================
# AI PROCESSING — live streamed progress screen
# =============================================================
def ai_stepper(phase: str) -> str:
    labels = ["Fetch mentions", "Filter & organize", "AI analysis", "Explore insights"]
    desc = ["YouTube + Hacker News", "Saved in SQL Server", "Ollama & SQL persistence", "Next phase"]
    status = ["done", "done", "done" if phase == "analyzed" else "active", "pending"]
    steps = "".join(
        f'<div class="bp-step bp-step-{state}"><span class="bp-step-circle">'
        f'{"✓" if state == "done" else i}</span><div><strong>{h(label)}</strong>'
        f'<small>{h(desc[i-1])}</small></div></div>'
        for i, (label, state) in enumerate(zip(labels, status), start=1)
    )
    return f'<div class="bp-stepper">{steps}</div>'


def ai_progress_html(metrics: dict[str, Any], stages: dict[str, str]) -> str:
    total = metrics.get("records_total", metrics.get("records_selected"))
    processed = int(metrics.get("records_processed", 0) or 0)
    pct = max(0.0, min(100.0, (100 * processed / total if total else 0.0)))
    if stages.get("summary") in ("started", "running"):
        status = "Generating Executive Summary"
        caption = "Record-level analysis is finished; generating a saved brand summary."
    elif stages.get("records") in ("started", "running", "completed"):
        status = "Analyzing Brand Mentions"
        caption = "Each mention is classified in one Ollama call; results are then stored in SQL Server."
    else:
        status = "Preparing AI Analysis"
        caption = "Finding previously unanalyzed records for the selected brand."
    selected_text = nice_num(total, unknown=True)
    return f'''
      <div class="bp-progress-main bp-ai-progress">
        <div class="bp-panel-top"><span class="bp-panel-title">✧ &nbsp; AI Processing Progress</span>
          <span class="bp-live-chip"><i></i> LIVE</span></div>
        <div class="bp-progress-inner">
          <div class="bp-progress-ring" style="--bp-progress:{pct:.2f}%">
            <div class="bp-progress-ring-inside"><strong>{pct:.0f}%</strong><small>Batch attempted</small></div>
          </div>
          <div class="bp-progress-info"><div class="bp-progress-status">{h(status)}</div>
            <p>{h(caption)}</p>
            <div class="bp-progress-count">{nice_num(processed)} / {selected_text} records attempted</div>
            <div class="bp-progress-caption">100% means every selected record was attempted; check success and failure counters below.</div>
          </div>
        </div>
        <div class="bp-processing-capabilities"><span>◇ Relevance</span><span>☺ Sentiment</span>
        <span>⬡ Topics</span><span>♡ Feedback</span><span>✧ Summary</span></div>
      </div>'''


def ai_processing_metrics(m: dict[str, Any]) -> str:
    items = [
        ("Successfully analyzed", m.get("analyzed"), "◎", "new", "Saved AI analysis"),
        ("Relevant in this batch", m.get("relevant_analyzed"), "◇", "old", "Of newly analyzed"),
        ("Topic associations", m.get("topics_extracted"), "⬡", "mint", "Extracted in this batch"),
        ("Feedback observations", (
            int(m.get("positive_feedback_extracted") or 0) + int(m.get("negative_feedback_extracted") or 0)
            if "positive_feedback_extracted" in m or "negative_feedback_extracted" in m else None
        ), "♡", "yt", "Positive + negative"),
    ]
    return '<div class="bp-metrics-grid">' + ''.join(
        metric_tile(name, nice_num(value, unknown=True), icon, cls, note)
        for name, value, icon, cls, note in items
    ) + '</div>'


def ai_activity_html(events: list[dict[str, Any]], running: bool, failed: bool = False) -> str:
    """Same historical event-state logic as collection, with an AI heading."""
    return activity_feed(events, running, failed=failed).replace("Live Activity Feed", "Live AI Processing Activity")


def ai_analysis_page(run: bool) -> None:
    brand = st.session_state.bp_brand
    st.markdown(
        '<div class="bp-aurora-hero"><div class="bp-eyebrow">AI-POWERED BRAND INTELLIGENCE</div>'
        '<h1 class="bp-page-title">Processing <span>AI Insights</span></h1>'
        f'<p class="bp-page-description">Analyzing discussions about <strong>{h(brand)}</strong> '
        'to extract relevance, sentiment, topics, and customer feedback.</p></div>',
        unsafe_allow_html=True,
    )
    stepper_ph = st.empty()
    left, right = st.columns([1.45, 1], gap="large", vertical_alignment="top")
    with left:
        progress_ph = st.empty()
        details_ph = st.empty()
    with right:
        activity_ph = st.empty()
        metrics_ph = st.empty()
    notice_ph = st.empty()

    def render_all():
        events = st.session_state.bp_ai_events
        stages = st.session_state.bp_ai_stages
        metrics = st.session_state.bp_ai_metrics
        stepper_ph.markdown(ai_stepper("analyzing"), unsafe_allow_html=True)
        progress_ph.markdown(ai_progress_html(metrics, stages), unsafe_allow_html=True)
        activity_ph.markdown(ai_activity_html(events, True), unsafe_allow_html=True)
        metrics_ph.markdown(ai_processing_metrics(metrics), unsafe_allow_html=True)
        details_ph.markdown('''<div class="bp-ai-details"><b>One inference per mention</b>
          <p>Ollama extracts relevance, overall sentiment, topic sentiments, and positive / negative feedback in one structured response. SQL Server stores the validated results.</p>
          </div>''', unsafe_allow_html=True)
        notice_ph.markdown('''<div class="bp-inline-notice">ⓘ &nbsp; Batch progress is based on attempted records.
          The final summary is generated only if no records remain pending (or an existing summary is reused).</div>''', unsafe_allow_html=True)

    render_all()
    if not run:
        st.warning("AI processing was interrupted (for example, by a browser rerun). Previously saved analyses remain in SQL Server. You can restart safely; only missing analyses are selected.")
        if st.button("← Back to collected mentions", key="interrupted_ai_back"):
            st.session_state.bp_phase = "collected"
            st.rerun()
        return

    st.session_state.bp_ai_run_pending = False

    def on_progress(event: dict[str, Any]):
        st.session_state.bp_ai_events.append(event)
        st.session_state.bp_ai_events = st.session_state.bp_ai_events[-70:]
        stage, status = event.get("stage"), event.get("status")
        if stage in AI_STAGES and status in ("started", "running", "completed", "failed"):
            st.session_state.bp_ai_stages[stage] = status
        metrics = event.get("metrics") or {}
        if isinstance(metrics, dict):
            st.session_state.bp_ai_metrics.update(metrics)
        render_all()

    try:
        # Import only when the AI-processing step actually begins; reuse the
        # previously tested Ollama implementation inside process.py.
        from process_with_progress import process_brand_with_progress
        result = process_brand_with_progress(
            brand_name=brand,
            max_records=st.session_state.bp_ai_max_records,
            progress_callback=on_progress,
        )
    except Exception as exc:
        st.session_state.bp_error = f"{type(exc).__name__}: {exc}"
        st.session_state.bp_error_origin = "analysis"
        st.session_state.bp_phase = "error"
    else:
        st.session_state.bp_ai_result = result
        st.session_state.bp_phase = "analyzed"
    st.rerun()


# =============================================================
# AI COMPLETE — standalone screen, not a modified progress screen
# =============================================================
def load_saved_brand_metrics():
    """Read dashboard KPIs already stored in SQL; no Ollama calls here.

    A read failure must not hide an otherwise successfully completed AI batch.
    """
    try:
        from database.analysis_repository import get_brand_id
        from database.insights_repository import (
            get_brand_overview,
            get_sentiment_distribution,
            get_executive_summary,
        )
        brand_id = get_brand_id(st.session_state.bp_brand)
        if brand_id is None:
            return {}, {}, None, "Brand was not found in SQL Server."
        return (
            get_brand_overview(brand_id),
            get_sentiment_distribution(brand_id),
            get_executive_summary(brand_id),
            None,
        )
    except Exception as exc:
        return {}, {}, None, f"Unable to load saved KPI preview: {type(exc).__name__}: {exc}"


def sentiment_donut(counts: dict[str, Any]) -> str:
    labels = ("positive", "negative", "neutral", "mixed")
    colors = ("#30cc91", "#fa5276", "#519afa", "#9665f9")
    values = [int(counts.get(k, 0) or 0) for k in labels]
    total = sum(values)
    fractions = [100*v/total if total else 0 for v in values]
    if total:
        parts, start = [], 0
        for color, fraction in zip(colors, fractions):
            end = start + fraction
            parts.append(f"{color} {start:.3f}% {end:.3f}%")
            start = end
        gradient = f'conic-gradient({", ".join(parts)})'
    else:
        gradient = "#edf1fb"
    rows = ''.join(
        f'<div class="bp-sentiment-row"><i style="background:{color}"></i><span>{h(key.title())}</span>'
        f'<b>{fraction:.1f}%</b><small>{nice_num(value)}</small></div>'
        for key, color, value, fraction in zip(labels, colors, values, fractions)
    )
    return f'''<div class="bp-chart-card bp-sentiment-summary"><div class="bp-chart-heading">Sentiment Distribution</div>
      <div class="bp-donut-flex"><div class="bp-donut" style="background:{gradient}">
        <div class="bp-donut-center"><strong>{nice_num(total)}</strong><small>Relevant mentions</small></div>
      </div><div class="bp-sentiment-legend">{rows}</div></div>
    </div>'''


def ai_complete_page() -> None:
    brand = st.session_state.bp_brand
    result = st.session_state.bp_ai_result or {}
    overview, sentiments, saved_summary, read_error = load_saved_brand_metrics()
    remaining = result.get("remaining")
    errors = int(result.get("failed", 0) or 0)
    summary_status = result.get("summary_status", "not_started")
    is_fully_analyzed = remaining == 0
    has_summary = saved_summary is not None
    finished_without_errors = is_fully_analyzed and errors == 0 and summary_status != "failed"

    label = "AI ANALYSIS COMPLETED" if is_fully_analyzed else "AI ANALYSIS BATCH COMPLETED"
    title = 'AI Processing <span>Complete</span>' if is_fully_analyzed else 'AI Batch <span>Complete</span>'
    subtitle = (
        'All currently collected mentions have completed AI processing.'
        if is_fully_analyzed else
        f'{nice_num(remaining, unknown=True)} brand-associated mentions are still awaiting analysis.'
    )
    st.markdown(
        f'<div class="bp-finish-hero"><div class="bp-finish-intro"><div class="bp-eyebrow">{label}</div>'
        f'<h1 class="bp-page-title">{title}</h1>'
        f'<p class="bp-page-description">{h(subtitle)} Review the extracted intelligence for '
        f'<strong>{h(brand)}</strong>.</p></div>'
        f'<div class="bp-brand-context"><span class="bp-brand-avatar">{h(brand[:1].upper())}</span>'
        f'<div><small>BRAND ANALYSIS</small><strong>{h(brand)}</strong>'
        f'<p>{"Completed" if is_fully_analyzed else "More analysis pending"}</p></div></div></div>',
        unsafe_allow_html=True,
    )
    if finished_without_errors:
        st.markdown('<div class="bp-success-banner">✓ &nbsp; AI analysis run completed successfully.</div>', unsafe_allow_html=True)
    else:
        reason = (f"{errors} record(s) failed during this run. " if errors else "")
        if not is_fully_analyzed:
            reason += f"{nice_num(remaining, unknown=True)} mentions remain unanalyzed. "
        if summary_status == "failed":
            reason += "Executive summary generation failed; retry when ready."
        st.warning(reason or "Some AI processing tasks need attention.")

    if read_error:
        st.warning(read_error)
    st.markdown(
        '<div class="bp-complete-cards bp-six-cards">'
        + metric_tile("Analyzed mentions", nice_num(overview.get("analyzed_mentions"), unknown=True), "◎", "new", "Saved across all runs")
        + metric_tile("Relevant mentions", nice_num(overview.get("relevant_mentions"), unknown=True), "◇", "old", "Brand-relevant analyzed")
        + metric_tile("Topics identified", nice_num(overview.get("total_topics"), unknown=True), "⬡", "mint", "Distinct topics")
        + metric_tile("Positive sentiment", (f'{overview["positive_percentage"]:.1f}%' if "positive_percentage" in overview else "—"), "☺", "mint", "Of relevant mentions")
        + metric_tile("Negative sentiment", (f'{overview["negative_percentage"]:.1f}%' if "negative_percentage" in overview else "—"), "☹", "yt", "Of relevant mentions")
        + metric_tile("Summary status", "Available" if has_summary else "Pending", "✧", "old", h(summary_status.replace("_", " ")))
        + '</div>', unsafe_allow_html=True,
    )
    left, right = st.columns([1.18, 1], gap="large", vertical_alignment="top")
    with left:
        preview = (saved_summary or {}).get("executive_summary") if isinstance(saved_summary, dict) else None
        preview = preview or "A saved executive summary is not available yet. When all mentions are processed, BrandPulse AI can generate the initial summary."
        shortened = preview[:610] + ("…" if len(preview) > 610 else "")
        st.markdown(
            '<div class="bp-summary-preview"><div class="bp-chart-heading">✧ &nbsp; AI Executive Summary Preview</div>'
            f'<p>{h(shortened)}</p><small>{"Saved executive summary" if has_summary else "Not generated yet"}'
            '</small></div>', unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="bp-batch-info"><strong>This AI processing run</strong>'
            f'<p>{nice_num(result.get("selected"))} records selected · '
            f'{nice_num(result.get("analyzed"))} saved · '
            f'{nice_num(result.get("skipped"))} skipped · '
            f'{nice_num(result.get("failed"))} failed.</p></div>', unsafe_allow_html=True,
        )
    with right:
        st.markdown(sentiment_donut(sentiments), unsafe_allow_html=True)

    st.markdown('<div class="bp-cta-spacer"></div>', unsafe_allow_html=True)
    primary, secondary = st.columns([2, 1], gap="large")
    with primary:
        if remaining is not None and remaining > 0:
            if st.button("✧  Process Next AI Batch   →", type="primary", use_container_width=True, key="next_batch"):
                start_ai_analysis()
                st.rerun()
        elif summary_status == "failed":
            if st.button("↻  Retry Executive Summary", type="primary", use_container_width=True, key="retry_summary"):
                start_ai_analysis()
                st.rerun()
        else:
            st.button("✦  Show Intelligence Dashboard — Next Phase", type="primary", disabled=True, use_container_width=True)
    with secondary:
        if st.button("← Analyze another brand", use_container_width=True, key="another_brand_analyzed"):
            reset_home()
            st.rerun()
    with st.expander("View AI processing activity", expanded=False):
        st.markdown(ai_activity_html(st.session_state.bp_ai_events, False), unsafe_allow_html=True)


def error_page() -> None:
    origin = st.session_state.bp_error_origin
    display = "AI analysis" if origin == "analysis" else "data collection"
    st.markdown(
        '<div class="bp-eyebrow">WORKFLOW INTERRUPTED</div>'
        f'<h1 class="bp-page-title">{h(display.title())} <span>Needs Attention</span></h1>',
        unsafe_allow_html=True,
    )
    st.error(st.session_state.bp_error or "An unexpected error occurred.")
    events = st.session_state.bp_ai_events if origin == "analysis" else st.session_state.bp_events
    st.markdown(
        ai_activity_html(events, False, failed=True) if origin == "analysis" else activity_feed(events, False, failed=True),
        unsafe_allow_html=True,
    )
    st.info("Previously committed data remains in SQL Server. Missing analyses can be retried; this screen will not silently rerun the failed operation.")
    if st.button("← Back to collected mentions" if origin == "analysis" else "← Return Home", use_container_width=False):
        if origin == "analysis":
            st.session_state.bp_phase = "collected"
            st.session_state.bp_error = ""
        else:
            reset_home()
        st.rerun()


def main() -> None:
    initialize_state()
    sidebar()
    topbar()
    phase = st.session_state.bp_phase
    if phase == "home":
        home_page()
    elif phase == "fetching":
        render_collection_screen(run=st.session_state.bp_run_pending)
    elif phase == "collected":
        collected_page()
    elif phase == "analyzing":
        ai_analysis_page(run=st.session_state.bp_ai_run_pending)
    elif phase == "analyzed":
        ai_complete_page()
    elif phase == "error":
        error_page()


if __name__ == "__main__":
    main()
