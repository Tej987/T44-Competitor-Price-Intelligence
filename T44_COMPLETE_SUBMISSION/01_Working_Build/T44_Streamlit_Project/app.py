from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analysis_core import (
    ai_prompt_templates,
    apply_filters,
    build_llm_prompt,
    build_observation_table,
    category_summary,
    category_week_matrix,
    data_quality_metrics,
    executive_action_items,
    generate_executive_summary,
    generate_verified_weekly_brief,
    make_export_workbook,
    persistent_action_table,
    platform_summary,
    product_summary,
    read_price_tracker,
    recommendation_table,
    summary_metrics,
    validate_input,
    verification_checks,
    weekly_trend,
)

# -----------------------------------------------------------------------------
# Page + visual system
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="T44 | Competitor Price Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

RED = "#E45756"
GREEN = "#2CA25F"
BLUE = "#3B82F6"
AMBER = "#D97706"
SLATE = "#64748B"
NAVY = "#0F2740"
BG = "#0E1117"

st.markdown(
    f"""
<style>
    .block-container {{padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1500px;}}
    [data-testid="stMetric"] {{
        background: linear-gradient(145deg, rgba(30,41,59,.78), rgba(15,23,42,.88));
        border: 1px solid rgba(148,163,184,.18);
        padding: 14px 16px;
        border-radius: 14px;
    }}
    [data-testid="stMetricLabel"] {{font-weight: 650;}}
    .hero {{
        padding: 22px 26px;
        border-radius: 18px;
        background: linear-gradient(115deg, #0F2740 0%, #173B5E 55%, #0F4C5C 100%);
        border: 1px solid rgba(255,255,255,.10);
        margin-bottom: 14px;
    }}
    .hero h1 {{margin: 0 0 7px 0; font-size: 2.15rem;}}
    .hero p {{margin: 0; color: #D7E3EF; font-size: 1.02rem;}}
    .section-note {{
        padding: 12px 14px; border-left: 4px solid {BLUE};
        background: rgba(59,130,246,.08); border-radius: 8px; margin: 8px 0 16px 0;
    }}
    .workflow {{
        border: 1px solid rgba(148,163,184,.18); border-radius: 14px;
        padding: 16px; background: rgba(30,41,59,.35); text-align: center;
        min-height: 98px;
    }}
    .workflow b {{font-size: 1.02rem;}}
    .tiny {{font-size:.86rem; color:#94A3B8;}}
    .status-good {{color:#86EFAC; font-weight:700;}}
    .status-warn {{color:#FCA5A5; font-weight:700;}}
    div[data-testid="stTabs"] button {{font-weight: 650;}}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
  <h1>📈 Competitor Price Intelligence</h1>
  <p>T44 working build • transparent benchmark calculations • decision-focused dashboard • verified LLM reporting workflow</p>
</div>
""",
    unsafe_allow_html=True,
)

DATA_PATH = Path(__file__).with_name("T44_Competitor_price_intelligence_brief.xlsx")

# -----------------------------------------------------------------------------
# Sidebar controls
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## Control Panel")
    uploaded = st.file_uploader("Upload T44 workbook", type=["xlsx"])
    st.caption("No upload? The bundled T44 workbook is used automatically.")

    st.markdown("### Decision rule")
    action_threshold = st.slider(
        "Review threshold |gap %|",
        min_value=1.0,
        max_value=20.0,
        value=5.0,
        step=0.5,
        help="This threshold prioritises human review. It does not trigger an automatic price change.",
    )
    top_n = st.slider("Top action items", 3, 10, 5, 1)

source = uploaded if uploaded is not None else DATA_PATH
try:
    raw_df = read_price_tracker(source)
except Exception as exc:
    st.error(f"Could not read the 'Price Tracker' sheet: {exc}")
    st.stop()

validation = validate_input(raw_df)
if not validation.ok:
    for msg in validation.messages:
        st.error(msg)
    st.stop()

obs, normalized = build_observation_table(raw_df)
if obs.empty:
    st.error("No complete Our Brand + Competitor A/B/C observations could be built.")
    st.stop()

with st.sidebar:
    st.markdown("### Filters")
    cats = st.multiselect("Category", sorted(obs["category"].dropna().unique()))
    plats = st.multiselect("Our Brand platform", sorted(obs["our_platform"].dropna().unique()))
    prods = st.multiselect("Product", sorted(obs["product"].dropna().unique()))
    st.caption("All dashboard numbers update with these filters.")

filtered = apply_filters(obs, cats, plats, prods)
if filtered.empty:
    st.warning("No observations match the current filters. Clear one or more filters.")
    st.stop()

m = summary_metrics(filtered)
dq = data_quality_metrics(raw_df, obs)
latest_week = pd.Timestamp(filtered["week_start"].max())
latest_filtered = filtered[filtered["week_start"] == latest_week]
lm = summary_metrics(latest_filtered)

# -----------------------------------------------------------------------------
# Headline KPIs
# -----------------------------------------------------------------------------
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Comparable observations", f"{m['observations']}")
k2.metric("Overpriced", f"{m['overpriced']}")
k3.metric("Underpriced", f"{m['underpriced']}")
k4.metric("Average gap", f"{m['avg_gap_pct']:+.1f}%")
k5.metric("Median gap", f"{m['median_gap_pct']:+.1f}%")
k6.metric("Same-platform coverage", f"{m['same_platform_coverage_pct']:.0f}%")

st.markdown(
    f"""
<div class="section-note">
<b>Benchmark:</b> Our Brand selling price − mean selling price of Competitor A, B and C within the same observation.
Positive gap = Our Brand is more expensive; negative gap = cheaper. The <b>±{action_threshold:.1f}%</b> threshold is a review rule, not an automatic pricing rule.
</div>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Helpers for charts/tables
# -----------------------------------------------------------------------------
def gap_color(values):
    return [RED if v > 0 else GREEN if v < 0 else SLATE for v in values]


def add_threshold_lines(fig, horizontal: bool = True):
    if horizontal:
        fig.add_hline(y=0, line_dash="dash", line_color=SLATE, line_width=1)
        fig.add_hline(y=action_threshold, line_dash="dot", line_color=RED, opacity=0.7)
        fig.add_hline(y=-action_threshold, line_dash="dot", line_color=GREEN, opacity=0.7)
    else:
        fig.add_vline(x=0, line_dash="dash", line_color=SLATE, line_width=1)
        fig.add_vline(x=action_threshold, line_dash="dot", line_color=RED, opacity=0.7)
        fig.add_vline(x=-action_threshold, line_dash="dot", line_color=GREEN, opacity=0.7)
    return fig


def style_gap_table(df: pd.DataFrame):
    formatters = {}
    for c in df.columns:
        if c.endswith("_inr") or "price_inr" in c or "gap_inr" in c:
            formatters[c] = "₹{:,.0f}"
        elif c.endswith("_pct") or "coverage_pct" in c:
            formatters[c] = "{:+.1f}%" if "gap" in c else "{:.1f}%"
        elif c == "week_start" or c == "latest_week":
            formatters[c] = lambda v: pd.Timestamp(v).strftime("%Y-%m-%d") if pd.notna(v) else "—"
    return df.style.format(formatters, na_rep="—")


def action_badge_table(df: pd.DataFrame):
    return style_gap_table(df)

# -----------------------------------------------------------------------------
# Tabs
# -----------------------------------------------------------------------------
tabs = st.tabs(
    [
        "🎯 Executive Dashboard",
        "🔎 Deep Dive",
        "🤖 Weekly Brief + AI",
        "🚦 Action Centre",
        "✅ Verification",
        "🧾 AI Use Log",
        "📦 Export & Methodology",
    ]
)

# =============================================================================
# 1. Executive Dashboard
# =============================================================================
with tabs[0]:
    st.subheader("What management should know")
    st.info(generate_executive_summary(filtered, action_threshold))

    st.markdown(f"### Latest week • {latest_week:%d %b %Y}")
    a, b, c, d, e = st.columns(5)
    a.metric("Observations", lm["observations"])
    b.metric("Overpriced", lm["overpriced"])
    c.metric("Underpriced", lm["underpriced"])
    d.metric("Average gap", f"{lm['avg_gap_pct']:+.1f}%")
    e.metric("Same-platform coverage", f"{lm['same_platform_coverage_pct']:.0f}%")

    st.markdown("### Action Centre — latest signals")
    actions = executive_action_items(latest_filtered, action_threshold, top_n)
    if actions.empty:
        st.success(f"No latest-week observations exceed the ±{action_threshold:.1f}% review threshold.")
    else:
        st.dataframe(action_badge_table(actions), use_container_width=True, hide_index=True)

    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("### Price-gap trend")
        trend = weekly_trend(filtered)
        fig_trend = go.Figure()
        fig_trend.add_trace(
            go.Scatter(
                x=trend["week_start"],
                y=trend["avg_gap_pct"],
                mode="lines+markers",
                name="Average gap %",
                line=dict(color=BLUE, width=3),
                marker=dict(size=8),
                hovertemplate="%{x|%d %b %Y}<br>Avg gap: %{y:+.1f}%<extra></extra>",
            )
        )
        fig_trend = add_threshold_lines(fig_trend, horizontal=True)
        fig_trend.update_layout(
            height=360,
            margin=dict(l=10, r=10, t=25, b=10),
            yaxis_title="Average price gap %",
            xaxis_title="Week",
            legend_orientation="h",
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    with right:
        st.markdown("### Category position")
        cat = category_summary(filtered)
        fig_cat = go.Figure(
            go.Bar(
                x=cat["category"],
                y=cat["avg_gap_pct"],
                marker_color=gap_color(cat["avg_gap_pct"]),
                text=[f"{v:+.1f}%" for v in cat["avg_gap_pct"]],
                textposition="outside",
                hovertemplate="%{x}<br>Avg gap: %{y:+.1f}%<extra></extra>",
            )
        )
        fig_cat = add_threshold_lines(fig_cat, horizontal=True)
        fig_cat.update_layout(
            height=360,
            margin=dict(l=10, r=10, t=25, b=10),
            yaxis_title="Average price gap %",
            xaxis_title="",
        )
        st.plotly_chart(fig_cat, use_container_width=True)

    st.markdown("### Top risks and opportunities")
    r1, r2 = st.columns(2)
    top_over = filtered.sort_values("price_gap_pct", ascending=False).head(top_n)
    top_under = filtered.sort_values("price_gap_pct", ascending=True).head(top_n)

    with r1:
        st.markdown("**🔴 Largest positive gaps**")
        fig_over = go.Figure(
            go.Bar(
                x=top_over["price_gap_pct"],
                y=top_over["product"],
                orientation="h",
                marker_color=RED,
                customdata=top_over[["our_price_inr", "competitor_avg_price_inr", "week_start"]],
                hovertemplate=(
                    "%{y}<br>Gap: %{x:+.1f}%<br>Our price: ₹%{customdata[0]:,.0f}"
                    "<br>Benchmark: ₹%{customdata[1]:,.0f}<br>Week: %{customdata[2]|%d %b %Y}<extra></extra>"
                ),
            )
        )
        fig_over = add_threshold_lines(fig_over, horizontal=False)
        fig_over.update_layout(height=340, xaxis_title="Gap %", yaxis_title="", margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_over, use_container_width=True)

    with r2:
        st.markdown("**🟢 Largest negative gaps**")
        fig_under = go.Figure(
            go.Bar(
                x=top_under["price_gap_pct"],
                y=top_under["product"],
                orientation="h",
                marker_color=GREEN,
                customdata=top_under[["our_price_inr", "competitor_avg_price_inr", "week_start"]],
                hovertemplate=(
                    "%{y}<br>Gap: %{x:+.1f}%<br>Our price: ₹%{customdata[0]:,.0f}"
                    "<br>Benchmark: ₹%{customdata[1]:,.0f}<br>Week: %{customdata[2]|%d %b %Y}<extra></extra>"
                ),
            )
        )
        fig_under = add_threshold_lines(fig_under, horizontal=False)
        fig_under.update_layout(height=340, xaxis_title="Gap %", yaxis_title="", margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_under, use_container_width=True)

    with st.expander("View complete product summary"):
        ps = product_summary(filtered)
        st.dataframe(style_gap_table(ps), use_container_width=True, hide_index=True)

# =============================================================================
# 2. Deep Dive
# =============================================================================
with tabs[1]:
    st.subheader("Category, platform, product and weekly analysis")

    c1, c2 = st.columns(2)
    with c1:
        cat = category_summary(filtered)
        st.markdown("#### Category summary")
        st.dataframe(style_gap_table(cat), use_container_width=True, hide_index=True)
    with c2:
        plat = platform_summary(filtered)
        st.markdown("#### Our Brand platform summary")
        st.dataframe(style_gap_table(plat), use_container_width=True, hide_index=True)
        st.caption("Platform results are descriptive. Competitor platforms can differ, so same-platform coverage is shown separately.")

    st.markdown("#### Category × week heatmap")
    matrix = category_week_matrix(filtered)
    if not matrix.empty:
        fig_heat = px.imshow(
            matrix,
            aspect="auto",
            color_continuous_scale=[(0, GREEN), (0.5, "#F8FAFC"), (1, RED)],
            color_continuous_midpoint=0,
            labels=dict(color="Gap %"),
        )
        fig_heat.update_layout(height=420, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig_heat, use_container_width=True)

    st.markdown("#### Persistent product signals")
    persistent = persistent_action_table(filtered, action_threshold)
    keep = [
        "category", "product", "observations", "avg_gap_pct", "latest_gap_pct",
        "same_platform_coverage_pct", "signal", "consistency", "recommended_action"
    ]
    st.dataframe(style_gap_table(persistent[keep]), use_container_width=True, hide_index=True)

    with st.expander("Observation-level audit table"):
        display_cols = [
            "observation_id", "week_start", "category", "product", "our_platform",
            "our_price_inr", "competitor_a_price_inr", "competitor_b_price_inr", "competitor_c_price_inr",
            "competitor_avg_price_inr", "price_gap_inr", "price_gap_pct", "position",
            "our_availability", "same_platform_competitor_count", "same_platform_gap_pct",
            "source_row_our_brand", "source_rows_competitors",
        ]
        view = filtered[display_cols].sort_values("price_gap_pct", ascending=False)
        st.dataframe(style_gap_table(view), use_container_width=True, hide_index=True)
        st.caption("Source-row fields make every calculation traceable to the original Price Tracker sheet.")

# =============================================================================
# 3. Weekly Brief + AI
# =============================================================================
with tabs[2]:
    st.subheader("Verified analytics → LLM narrative → human verification")

    flow = [
        ("400 source rows", "Raw Price Tracker"),
        ("100 observations", "Our Brand + A/B/C"),
        ("Deterministic maths", "Benchmark + gap %"),
        ("Verified summary", "Only checked numbers"),
        ("LLM narrative", "Management brief"),
        ("Human review", "Verify every claim"),
    ]
    flow_cols = st.columns(6)
    for col, (title, sub) in zip(flow_cols, flow):
        col.markdown(f'<div class="workflow"><b>{title}</b><br><span class="tiny">{sub}</span></div>', unsafe_allow_html=True)

    weeks = sorted(filtered["week_start"].dropna().unique(), reverse=True)
    selected_week = st.selectbox(
        "Select week for the brief",
        options=weeks,
        format_func=lambda x: pd.Timestamp(x).strftime("%d %b %Y"),
    )

    brief = generate_verified_weekly_brief(filtered, selected_week)
    left, right = st.columns([1.05, 0.95])
    with left:
        st.markdown("#### Verified baseline brief")
        st.text_area("Verified brief", brief, height=420, label_visibility="collapsed")
        st.download_button(
            "Download verified brief (.txt)",
            data=brief.encode("utf-8"),
            file_name=f"T44_weekly_brief_{pd.Timestamp(selected_week):%Y-%m-%d}.txt",
            mime="text/plain",
        )
    with right:
        st.markdown("#### LLM prompt")
        prompt = build_llm_prompt(filtered, selected_week)
        st.code(prompt, language="text")
        st.caption("Run this prompt in ChatGPT/Gemini/Claude, save evidence, then verify its numeric claims against the baseline.")

    st.markdown("#### AI output claim extractor")
    ai_text = st.text_area(
        "Paste the LLM-generated brief here",
        height=190,
        placeholder="Paste the AI-generated weekly brief here...",
    )
    if ai_text.strip():
        percents = re.findall(r"[-+]?\d+(?:\.\d+)?\s*%", ai_text)
        rupees = re.findall(r"(?:₹|Rs\.?\s*)\s*\d[\d,]*(?:\.\d+)?", ai_text, flags=re.I)
        counts = re.findall(r"(?<![A-Za-z₹])\b\d+(?:\.\d+)?\b", ai_text)
        q1, q2, q3 = st.columns(3)
        q1.write("**Percentage claims**")
        q1.write(percents or "None")
        q2.write("**Rupee claims**")
        q2.write(rupees or "None")
        q3.write("**Other numbers**")
        q3.write(counts[:40] or "None")
        st.warning("This extracts claims; it does not certify them. Compare every number with the verified brief/tables before using the AI output.")

# =============================================================================
# 4. Action Centre
# =============================================================================
with tabs[3]:
    st.subheader("Pricing review queue")
    st.write(
        f"The app prioritises observations with |gap| ≥ **{action_threshold:.1f}%**. "
        "Actions remain recommendations for human review because margin, promotions, inventory and platform comparability are not fully captured here."
    )

    rec = recommendation_table(filtered, action_threshold)
    high = int((rec["priority"] == "High").sum()) if not rec.empty else 0
    med = int((rec["priority"] == "Medium").sum()) if not rec.empty else 0
    low = int((rec["priority"] == "Low").sum()) if not rec.empty else 0
    x1, x2, x3 = st.columns(3)
    x1.metric("High priority", high)
    x2.metric("Medium priority", med)
    x3.metric("Monitor", low)

    priorities = st.multiselect("Show priority", ["High", "Medium", "Low"], default=["High", "Medium"])
    rec_view = rec[rec["priority"].isin(priorities)] if priorities else rec
    st.dataframe(style_gap_table(rec_view), use_container_width=True, hide_index=True)

    st.markdown("#### Persistent product-level review")
    persistent = persistent_action_table(filtered, action_threshold)
    st.dataframe(
        style_gap_table(
            persistent[[
                "category", "product", "observations", "avg_gap_pct", "latest_gap_pct",
                "signal", "consistency", "same_platform_coverage_pct", "recommended_action"
            ]]
        ),
        use_container_width=True,
        hide_index=True,
    )

# =============================================================================
# 5. Verification
# =============================================================================
with tabs[4]:
    st.subheader("Correctness, traceability and data quality")

    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("Source rows", dq["source_rows"])
    d2.metric("Complete observations", dq["complete_observations"])
    d3.metric("Weeks", dq["weeks"])
    d4.metric("Missing prices", dq["missing_prices"])
    d5.metric("Same-platform coverage", f"{dq['same_platform_coverage_pct']:.0f}%")

    checks = verification_checks(raw_df, normalized, obs)
    st.dataframe(checks, use_container_width=True, hide_index=True)
    all_pass = bool((checks["status"] == "PASS").all())
    if all_pass:
        st.success("All programmed verification checks passed for the supplied T44 workbook.")
    else:
        st.warning("At least one verification check needs review.")

    st.markdown("#### Manual spot-check — benchmark ingredients")
    idx = [0, len(obs) // 2, len(obs) - 1]
    sample = obs.iloc[idx][[
        "observation_id", "week_start", "product", "our_price_inr",
        "competitor_a_price_inr", "competitor_b_price_inr", "competitor_c_price_inr",
        "competitor_avg_price_inr", "price_gap_inr", "price_gap_pct",
        "source_row_our_brand", "competitor_a_source_row", "competitor_b_source_row", "competitor_c_source_row",
    ]]
    st.dataframe(style_gap_table(sample), use_container_width=True, hide_index=True)
    st.code(
        "Competitor benchmark = (A + B + C) / 3\n"
        "Price gap (₹)       = Our Brand price - competitor benchmark\n"
        "Price gap (%)       = Price gap / competitor benchmark × 100",
        language="text",
    )

    st.markdown("#### Why same-platform coverage matters")
    st.write(
        f"Only **{dq['same_platform_coverage_pct']:.0f}%** of observations have at least one competitor on the same platform as Our Brand. "
        "Therefore, the main benchmark is a broad market comparison, while same-platform gaps are reported as a stricter supporting check rather than pretending every offer is perfectly comparable."
    )

# =============================================================================
# 6. AI Use Log
# =============================================================================
with tabs[5]:
    st.subheader("Documented AI Use Log — 15 project interactions")
    st.info(
        "These are the actual AI-assisted steps used while building and reviewing this T44 project. "
        "Python/Excel remained the source of truth for calculations; AI outputs were reviewed before acceptance."
    )

    documented_log = pd.DataFrame(
        [
            [1, "2026-10-01", "ChatGPT", "How to download this full workbook all things all tabs",
             "Explained that .xlsx preserves all workbook tabs while CSV does not.",
             "Downloaded the full workbook so the Task Brief, Price Tracker and AI Use Log remained together.",
             "Kept", "AI_Evidence_Transcript.pdf - Entry 01"],
            [2, "2026-10-01", "ChatGPT", "See my tasks and help me with it",
             "Identified T44, the price-intelligence objective, required deliverables and rubric.",
             "Verified the assignment details against the Task Brief before proceeding.",
             "Kept", "AI_Evidence_Transcript.pdf - Entry 02"],
            [3, "2026-10-01", "ChatGPT", "See",
             "Analysed the actual T44 workbook and produced an initial workbook-oriented solution.",
             "I rejected a static-only submission as too weak for the working-build criterion and moved to a live app.",
             "Partly kept", "AI_Evidence_Transcript.pdf - Entry 03"],
            [4, "2026-10-01", "ChatGPT", "Bro we have to code also wtf ??",
             "Clarified that coding was not explicitly mandatory, but a Streamlit build would strengthen the end-to-end demo.",
             "I chose to build a coded Streamlit application rather than rely only on Excel.",
             "Kept", "AI_Evidence_Transcript.pdf - Entry 04"],
            [5, "2026-10-01", "ChatGPT", "Yes do it now",
             "Generated the first Streamlit implementation around the real T44 dataset and deterministic price-gap logic.",
             "I ran it locally and moved into testing/debugging instead of accepting the first generated build.",
             "Kept", "AI_Evidence_Transcript.pdf - Entry 05"],
            [6, "2026-10-01", "ChatGPT", "What to do now that i opeened it in vs code",
             "Provided the exact VS Code terminal workflow and explained that app.py should be launched using Streamlit.",
             "I installed dependencies and launched the application locally.",
             "Kept", "AI_Evidence_Transcript.pdf - Entry 06"],
            [7, "2026-10-01", "ChatGPT", "It worked but this came at end",
             "Diagnosed the missing xlsxwriter package from the displayed traceback.",
             "I installed xlsxwriter and added it to the requirements so Excel export would work.",
             "Kept", "AI_Evidence_Transcript.pdf - Entry 07"],
            [8, "2026-10-01", "ChatGPT", "See this video what improvement we can do here",
             "Reviewed V1 and identified presentation weaknesses: clutter, weak action emphasis and insufficient visual signalling.",
             "I requested a second iteration with executive KPIs, action centre, threshold guides, AI workflow and stronger verification.",
             "Kept", "AI_Evidence_Transcript.pdf - Entry 08"],
            [9, "2026-10-01", "ChatGPT", "so give me updated best code include everything",
             "Produced V2 with an executive dashboard, latest-week KPIs, risk/opportunity views, verification and improved export.",
             "I tested V2 locally before treating the build as complete.",
             "Kept", "AI_Evidence_Transcript.pdf - Entry 09"],
            [10, "2026-10-01", "ChatGPT", "Updated Command",
             "Adjusted the run commands to the actual local project path.",
             "I used the corrected command and confirmed the app launched successfully at localhost:8501.",
             "Kept", "AI_Evidence_Transcript.pdf - Entry 10"],
            [11, "2026-10-04", "ChatGPT", "So i need to upload it o github should i check it once",
             "Recommended a final QA sequence covering app launch, filters, exports, refresh and the automated core test.",
             "I ran test_core.py and manually checked the app before preparing the repository.",
             "Kept", "AI_Evidence_Transcript.pdf - Entry 11"],
            [12, "2026-10-04", "ChatGPT", "should i test this ouput came",
             "Reviewed the rendered dashboard output and highlighted both correct results and interpretation/print-layout cautions.",
             "I ran the formal calculation test rather than relying only on visual inspection.",
             "Kept", "AI_Evidence_Transcript.pdf - Entry 12"],
            [13, "2026-10-04", "ChatGPT", "all good but it is using my excel sheet or not cause we have an upload option",
             "Verified that the bundled T44 workbook is used automatically when no file is uploaded, while upload acts as an override.",
             "I kept the upload feature because it makes the tool reusable while preserving the assigned dataset as the default.",
             "Kept", "AI_Evidence_Transcript.pdf - Entry 13"],
            [14, "2026-10-04", "ChatGPT", "So i can upload this?",
             "Reviewed the package and found cleanup issues such as __pycache__ and a machine-specific README path.",
             "I cleaned the repository package and added .gitignore before publishing.",
             "Kept", "AI_Evidence_Transcript.pdf - Entry 14"],
            [15, "2026-10-04", "ChatGPT", "but we need some more files written in instruction right like  reprt AI prompt used etc?",
             "Re-read the Task Brief and confirmed all four required submission items, including a 15-entry AI log and 3–5 page report.",
             "I expanded the submission from code-only to a complete package with workbook, report, AI evidence and demo material.",
             "Kept", "AI_Evidence_Transcript.pdf - Entry 15"],
        ],
        columns=[
            "entry", "date", "tool", "prompt", "what_ai_produced",
            "verification_or_change", "decision", "evidence_reference"
        ],
    )

    # Keep the documented log in session state so the exported workbook
    # contains the same 15 entries shown on screen.
    st.session_state.ai_log = documented_log.copy()

    st.dataframe(
        documented_log,
        use_container_width=True,
        hide_index=True,
        column_config={
            "entry": st.column_config.NumberColumn("#", width="small"),
            "date": st.column_config.TextColumn("Date", width="small"),
            "tool": st.column_config.TextColumn("Tool", width="small"),
            "prompt": st.column_config.TextColumn("Actual prompt", width="large"),
            "what_ai_produced": st.column_config.TextColumn("What AI produced", width="large"),
            "verification_or_change": st.column_config.TextColumn("How I verified / what I changed", width="large"),
            "decision": st.column_config.TextColumn("Decision", width="small"),
            "evidence_reference": st.column_config.TextColumn("Evidence reference", width="medium"),
        },
    )

    st.caption(
        "Evidence is documented in AI_Evidence_Transcript.pdf. "
        "No screenshot or shared-chat link is claimed where one was not actually captured."
    )

    st.download_button(
        "Download documented AI Use Log (.csv)",
        data=documented_log.to_csv(index=False).encode("utf-8-sig"),
        file_name="T44_AI_Use_Log.csv",
        mime="text/csv",
    )

# =============================================================================
# 7. Export + Methodology
# =============================================================================
with tabs[6]:
    st.subheader("Submission package")

    selected_export_week = latest_week
    export_bytes = make_export_workbook(
        raw_df,
        obs,
        action_threshold,
        selected_export_week,
        st.session_state.get("ai_log"),
    )
    e1, e2, e3 = st.columns(3)
    e1.download_button(
        "⬇️ Complete analysis workbook",
        data=export_bytes,
        file_name="T44_Competitor_Price_Intelligence_Analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    e2.download_button(
        "⬇️ Recommendations CSV",
        data=recommendation_table(obs, action_threshold).to_csv(index=False).encode("utf-8-sig"),
        file_name="T44_Pricing_Recommendations.csv",
        mime="text/csv",
        use_container_width=True,
    )
    e3.download_button(
        "⬇️ Latest weekly brief",
        data=generate_verified_weekly_brief(obs, obs["week_start"].max()).encode("utf-8"),
        file_name="T44_Latest_Weekly_Brief.txt",
        mime="text/plain",
        use_container_width=True,
    )

    st.markdown("### Methodology")
    st.markdown(
        """
1. **Observation construction:** one Our Brand row is paired with Competitor A, B and C for the same week, category, product and occurrence number.
2. **Competitor benchmark:** arithmetic mean of the three competitor selling prices.
3. **Price gap:** `Our Brand price − competitor benchmark`.
4. **Normalized gap:** `price gap / competitor benchmark × 100`.
5. **Decision threshold:** absolute gap is used only to prioritise review; it does not automatically change price.
6. **Same-platform control:** same-platform competitor coverage and gap are reported separately because marketplace, own-website and quick-commerce offers may not be directly equivalent.
7. **AI separation:** Python performs deterministic calculations; an LLM is used only to convert verified analytical outputs into a management-oriented narrative.
8. **Human verification:** every numeric claim in the LLM-generated brief should be checked against the verified baseline before submission.
        """
    )

    st.markdown("### Limitations")
    st.markdown(
        """
- Price alone does not capture margin, shipping, coupons, bundles, loyalty benefits or all promotion mechanics.
- Availability can differ between sellers and may explain some extreme gaps.
- Cross-platform observations are useful market signals but are not perfectly like-for-like comparisons.
- Repeated product observations strengthen evidence, but the dataset is still a limited academic sample.
- Recommendations are decision aids, not automatic commercial actions.
        """
    )

st.divider()
st.caption("T44 • Streamlit + Python • deterministic calculations + verified LLM-assisted reporting • all metrics computed from the workbook")
