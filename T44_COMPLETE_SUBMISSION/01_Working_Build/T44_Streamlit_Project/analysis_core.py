from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "week_start",
    "category",
    "product",
    "seller",
    "platform",
    "selling_price_inr",
    "mrp_inr",
    "availability",
    "avg_rating",
    "rating_count",
]
EXPECTED_SELLERS = {"Our Brand", "Competitor A", "Competitor B", "Competitor C"}
COMPETITORS = ["Competitor A", "Competitor B", "Competitor C"]


@dataclass
class ValidationResult:
    ok: bool
    messages: List[str]


def read_price_tracker(source) -> pd.DataFrame:
    """Read the Price Tracker sheet from a file path or uploaded file-like object."""
    df = pd.read_excel(source, sheet_name="Price Tracker", engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def validate_input(df: pd.DataFrame) -> ValidationResult:
    messages: List[str] = []
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return ValidationResult(False, [f"Missing required columns: {', '.join(missing)}"])

    if df.empty:
        return ValidationResult(False, ["Price Tracker is empty."])

    sellers = set(df["seller"].dropna().astype(str).unique())
    if not EXPECTED_SELLERS.issubset(sellers):
        messages.append(
            "Expected sellers are not all present. Found: " + ", ".join(sorted(sellers))
        )

    for col in ["selling_price_inr", "mrp_inr"]:
        bad = pd.to_numeric(df[col], errors="coerce").isna().sum()
        if bad:
            messages.append(f"{col}: {bad} non-numeric/missing value(s).")

    if len(df) % 4 != 0:
        messages.append(
            f"Row count is {len(df)}, not a multiple of 4. Pairing will still be attempted using keys and occurrence order."
        )

    if not messages:
        messages.append("Input schema, seller set and core price fields look valid.")
    return ValidationResult(True, messages)


def _add_occurrence_index(df: pd.DataFrame) -> pd.DataFrame:
    """Create a stable occurrence number so repeated product/week blocks are not collapsed."""
    out = df.copy().reset_index(drop=False).rename(columns={"index": "source_index"})
    out["source_row"] = out["source_index"] + 2  # Excel row number; header is row 1.
    out["week_start"] = pd.to_datetime(out["week_start"], errors="coerce")
    for col in ["selling_price_inr", "mrp_inr", "avg_rating", "rating_count"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    grp_cols = ["week_start", "category", "product", "seller"]
    out["occurrence"] = out.groupby(grp_cols, dropna=False).cumcount() + 1
    return out


def build_observation_table(raw_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Convert source rows into comparable observations.

    One observation contains exactly one Our Brand row plus Competitor A/B/C for
    the same week/category/product/occurrence. The benchmark is the arithmetic
    mean of the three competitor selling prices.
    """
    df = _add_occurrence_index(raw_df)
    group_cols = ["week_start", "category", "product", "occurrence"]

    records: List[Dict] = []
    for key, g in df.groupby(group_cols, sort=False, dropna=False):
        ours = g[g["seller"] == "Our Brand"]
        comp = g[g["seller"].isin(COMPETITORS)]
        sellers = set(g["seller"].astype(str))

        if len(ours) != 1 or len(comp) != 3 or not EXPECTED_SELLERS.issubset(sellers):
            continue

        our = ours.iloc[0]
        comp_by_seller = comp.set_index("seller")
        comp_prices = comp["selling_price_inr"].astype(float)
        comp_avg = float(comp_prices.mean())
        comp_min = float(comp_prices.min())
        comp_max = float(comp_prices.max())
        our_price = float(our["selling_price_inr"])
        gap = our_price - comp_avg
        gap_pct = (gap / comp_avg * 100.0) if comp_avg else np.nan

        same = comp[comp["platform"] == our["platform"]]
        same_count = int(len(same))
        same_avg = float(same["selling_price_inr"].mean()) if same_count else np.nan
        same_gap = our_price - same_avg if same_count else np.nan
        same_gap_pct = (same_gap / same_avg * 100.0) if same_count and same_avg else np.nan

        our_mrp = float(our["mrp_inr"]) if pd.notna(our["mrp_inr"]) else np.nan
        our_discount_pct = (
            (our_mrp - our_price) / our_mrp * 100.0
            if our_mrp and pd.notna(our_mrp)
            else np.nan
        )

        position = "Overpriced" if gap > 0 else ("Underpriced" if gap < 0 else "At benchmark")

        rec = {
            "week_start": key[0],
            "category": key[1],
            "product": key[2],
            "occurrence": key[3],
            "observation_id": f"OBS-{len(records) + 1:03d}",
            "our_platform": our["platform"],
            "our_price_inr": our_price,
            "our_mrp_inr": our_mrp,
            "our_discount_pct": our_discount_pct,
            "our_availability": our["availability"],
            "our_rating": our["avg_rating"],
            "our_rating_count": our["rating_count"],
            "competitor_avg_price_inr": comp_avg,
            "competitor_min_price_inr": comp_min,
            "competitor_max_price_inr": comp_max,
            "price_gap_inr": gap,
            "price_gap_pct": gap_pct,
            "position": position,
            "same_platform_competitor_count": same_count,
            "same_platform_competitor_avg_price_inr": same_avg,
            "same_platform_gap_inr": same_gap,
            "same_platform_gap_pct": same_gap_pct,
            "source_row_our_brand": int(our["source_row"]),
            "source_rows_competitors": ", ".join(str(int(x)) for x in comp["source_row"].tolist()),
        }

        # Transparent benchmark ingredients for live-demo spot checking.
        for seller in COMPETITORS:
            row = comp_by_seller.loc[seller]
            safe = seller.lower().replace(" ", "_")
            rec[f"{safe}_price_inr"] = float(row["selling_price_inr"])
            rec[f"{safe}_platform"] = row["platform"]
            rec[f"{safe}_availability"] = row["availability"]
            rec[f"{safe}_source_row"] = int(row["source_row"])

        records.append(rec)

    obs = pd.DataFrame(records)
    if not obs.empty:
        obs = obs.sort_values(
            ["week_start", "category", "product", "observation_id"]
        ).reset_index(drop=True)
    return obs, df


def apply_filters(
    obs: pd.DataFrame,
    categories: Optional[Iterable[str]] = None,
    platforms: Optional[Iterable[str]] = None,
    products: Optional[Iterable[str]] = None,
    week_start: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    out = obs.copy()
    if categories:
        out = out[out["category"].isin(list(categories))]
    if platforms:
        out = out[out["our_platform"].isin(list(platforms))]
    if products:
        out = out[out["product"].isin(list(products))]
    if week_start is not None:
        out = out[out["week_start"] == pd.Timestamp(week_start)]
    return out


def summary_metrics(obs: pd.DataFrame) -> Dict[str, float]:
    if obs.empty:
        return {
            "observations": 0,
            "overpriced": 0,
            "underpriced": 0,
            "at_benchmark": 0,
            "avg_gap_pct": np.nan,
            "median_gap_pct": np.nan,
            "avg_abs_gap_pct": np.nan,
            "same_platform_coverage_pct": np.nan,
        }
    return {
        "observations": int(len(obs)),
        "overpriced": int((obs["price_gap_inr"] > 0).sum()),
        "underpriced": int((obs["price_gap_inr"] < 0).sum()),
        "at_benchmark": int((obs["price_gap_inr"] == 0).sum()),
        "avg_gap_pct": float(obs["price_gap_pct"].mean()),
        "median_gap_pct": float(obs["price_gap_pct"].median()),
        "avg_abs_gap_pct": float(obs["price_gap_pct"].abs().mean()),
        "same_platform_coverage_pct": float(
            (obs["same_platform_competitor_count"] > 0).mean() * 100
        ),
    }


def data_quality_metrics(raw_df: pd.DataFrame, obs: pd.DataFrame) -> Dict[str, float]:
    raw_prices = pd.to_numeric(raw_df["selling_price_inr"], errors="coerce")
    expected_observations = len(raw_df) / 4 if len(raw_df) else 0
    return {
        "source_rows": int(len(raw_df)),
        "complete_observations": int(len(obs)),
        "expected_observations": int(expected_observations) if expected_observations.is_integer() else expected_observations,
        "missing_prices": int(raw_prices.isna().sum()),
        "same_platform_coverage_pct": float(
            (obs["same_platform_competitor_count"] > 0).mean() * 100
        ) if not obs.empty else np.nan,
        "weeks": int(obs["week_start"].nunique()) if not obs.empty else 0,
    }


def _summary_table(obs: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if obs.empty:
        return pd.DataFrame()
    g = obs.groupby(group_col, dropna=False)
    out = g.agg(
        observations=("observation_id", "count"),
        avg_our_price_inr=("our_price_inr", "mean"),
        avg_competitor_price_inr=("competitor_avg_price_inr", "mean"),
        avg_gap_inr=("price_gap_inr", "mean"),
        avg_gap_pct=("price_gap_pct", "mean"),
        median_gap_pct=("price_gap_pct", "median"),
        avg_abs_gap_pct=("price_gap_pct", lambda s: s.abs().mean()),
        same_platform_coverage_pct=(
            "same_platform_competitor_count",
            lambda s: (s > 0).mean() * 100,
        ),
    ).reset_index()
    pos = g["price_gap_inr"].agg(
        overpriced=lambda s: int((s > 0).sum()),
        underpriced=lambda s: int((s < 0).sum()),
        at_benchmark=lambda s: int((s == 0).sum()),
    ).reset_index()
    out = out.merge(pos, on=group_col, how="left")
    return out.sort_values("avg_gap_pct", ascending=False).reset_index(drop=True)


def category_summary(obs: pd.DataFrame) -> pd.DataFrame:
    return _summary_table(obs, "category")


def platform_summary(obs: pd.DataFrame) -> pd.DataFrame:
    return _summary_table(obs, "our_platform")


def product_summary(obs: pd.DataFrame) -> pd.DataFrame:
    if obs.empty:
        return pd.DataFrame()
    g = obs.groupby(["category", "product"], dropna=False)
    out = g.agg(
        observations=("observation_id", "count"),
        avg_gap_pct=("price_gap_pct", "mean"),
        median_gap_pct=("price_gap_pct", "median"),
        avg_abs_gap_pct=("price_gap_pct", lambda s: s.abs().mean()),
        avg_our_price_inr=("our_price_inr", "mean"),
        avg_competitor_price_inr=("competitor_avg_price_inr", "mean"),
        latest_week=("week_start", "max"),
        same_platform_coverage_pct=(
            "same_platform_competitor_count",
            lambda s: (s > 0).mean() * 100,
        ),
    ).reset_index()

    latest_rows = (
        obs.sort_values(["week_start", "observation_id"])
        .groupby(["category", "product"], as_index=False)
        .tail(1)[["category", "product", "price_gap_pct", "our_price_inr", "competitor_avg_price_inr"]]
        .rename(
            columns={
                "price_gap_pct": "latest_gap_pct",
                "our_price_inr": "latest_our_price_inr",
                "competitor_avg_price_inr": "latest_competitor_price_inr",
            }
        )
    )
    out = out.merge(latest_rows, on=["category", "product"], how="left")
    return out.sort_values("avg_gap_pct", ascending=False).reset_index(drop=True)


def weekly_trend(obs: pd.DataFrame) -> pd.DataFrame:
    if obs.empty:
        return pd.DataFrame()
    g = obs.groupby("week_start", dropna=False)
    out = g.agg(
        observations=("observation_id", "count"),
        avg_gap_pct=("price_gap_pct", "mean"),
        median_gap_pct=("price_gap_pct", "median"),
        avg_abs_gap_pct=("price_gap_pct", lambda s: s.abs().mean()),
        overpriced=("price_gap_inr", lambda s: int((s > 0).sum())),
        underpriced=("price_gap_inr", lambda s: int((s < 0).sum())),
    ).reset_index()
    return out.sort_values("week_start").reset_index(drop=True)


def category_week_matrix(obs: pd.DataFrame) -> pd.DataFrame:
    if obs.empty:
        return pd.DataFrame()
    return obs.pivot_table(
        index="category",
        columns="week_start",
        values="price_gap_pct",
        aggfunc="mean",
    ).sort_index()


def week_summary(obs: pd.DataFrame, week: pd.Timestamp) -> Dict:
    w = obs[obs["week_start"] == pd.Timestamp(week)].copy()
    metrics = summary_metrics(w)
    metrics["week"] = pd.Timestamp(week)
    metrics["category_summary"] = category_summary(w)
    metrics["product_summary"] = product_summary(w)
    metrics["rows"] = w.sort_values("price_gap_pct", ascending=False)
    return metrics


def persistent_action_table(obs: pd.DataFrame, threshold_pct: float = 5.0) -> pd.DataFrame:
    """Aggregate repeated observations to surface persistent product signals."""
    ps = product_summary(obs)
    if ps.empty:
        return ps

    ps = ps.copy()
    ps["signal"] = np.select(
        [ps["avg_gap_pct"] >= threshold_pct, ps["avg_gap_pct"] <= -threshold_pct],
        ["Persistent premium", "Persistent discount"],
        default="Near benchmark",
    )

    ps["consistency"] = np.where(
        ps["observations"] >= 4,
        "Higher evidence",
        np.where(ps["observations"] >= 2, "Moderate evidence", "Single observation"),
    )

    def action(row) -> str:
        if row["avg_gap_pct"] >= threshold_pct:
            return "Review price/promotion; retain premium only with a clear value or margin justification."
        if row["avg_gap_pct"] <= -threshold_pct:
            return "Check margin headroom; maintain discount if it is intentionally driving traffic or conversion."
        return "Monitor; no immediate pricing action from price-gap evidence alone."

    ps["recommended_action"] = ps.apply(action, axis=1)
    ps["priority_score"] = ps["avg_gap_pct"].abs() * (1 + np.minimum(ps["observations"], 5) / 10)
    return ps.sort_values("priority_score", ascending=False).reset_index(drop=True)


def executive_action_items(
    obs: pd.DataFrame, threshold_pct: float = 5.0, top_n: int = 5
) -> pd.DataFrame:
    """Return concise observation-level items for the dashboard Action Centre."""
    if obs.empty:
        return pd.DataFrame()
    out = obs.copy()
    out["abs_gap_pct"] = out["price_gap_pct"].abs()
    out = out[out["abs_gap_pct"] >= threshold_pct].copy()
    if out.empty:
        return pd.DataFrame()

    high_cutoff = max(10.0, threshold_pct * 1.5)
    out["priority"] = np.where(
        out["abs_gap_pct"] >= high_cutoff,
        "High",
        "Medium",
    )
    out["signal"] = np.where(
        out["price_gap_pct"] > 0,
        "Overpriced vs benchmark",
        "Underpriced vs benchmark",
    )

    def action(row) -> str:
        if row["price_gap_pct"] > 0:
            base = "Review reduction/promotion or document why the premium is justified."
        else:
            base = "Check whether margin can be improved without hurting the pricing strategy."
        if row["same_platform_competitor_count"] > 0:
            return base + " Same-platform evidence is available."
        return base + " Cross-platform signal only; validate before acting."

    out["recommended_action"] = out.apply(action, axis=1)
    out["priority_rank"] = out["priority"].map({"High": 0, "Medium": 1}).fillna(2)
    cols = [
        "priority",
        "week_start",
        "category",
        "product",
        "our_platform",
        "our_price_inr",
        "competitor_avg_price_inr",
        "price_gap_pct",
        "signal",
        "same_platform_competitor_count",
        "recommended_action",
    ]
    return (
        out.sort_values(["priority_rank", "abs_gap_pct"], ascending=[True, False])
        .head(top_n)[cols]
        .reset_index(drop=True)
    )


def generate_executive_summary(obs: pd.DataFrame, threshold_pct: float = 5.0) -> str:
    if obs.empty:
        return "No observations are available under the current filters."
    m = summary_metrics(obs)
    cat = category_summary(obs)
    products = persistent_action_table(obs, threshold_pct)
    latest_week = pd.Timestamp(obs["week_start"].max())
    latest = obs[obs["week_start"] == latest_week]
    lm = summary_metrics(latest)

    direction = "below" if m["avg_gap_pct"] < 0 else "above"
    cat_text = ""
    if not cat.empty:
        high = cat.iloc[0]
        low = cat.iloc[-1]
        cat_text = (
            f" {high['category']} has the highest category-level average gap ({high['avg_gap_pct']:+.1f}%), "
            f"while {low['category']} has the lowest ({low['avg_gap_pct']:+.1f}%)."
        )

    action_count = int((obs["price_gap_pct"].abs() >= threshold_pct).sum())
    prod_text = ""
    if not products.empty:
        p = products.iloc[0]
        prod_text = (
            f" The strongest persistent product signal is {p['product']} at {p['avg_gap_pct']:+.1f}% "
            f"on average across {int(p['observations'])} observation(s)."
        )

    return (
        f"Across {m['observations']} comparable observations, Our Brand is on average "
        f"{abs(m['avg_gap_pct']):.1f}% {direction} the three-competitor benchmark. "
        f"{action_count} observation(s) exceed the ±{threshold_pct:.1f}% review threshold."
        f"{cat_text} In the latest week ({latest_week:%d %b %Y}), {lm['overpriced']} observation(s) are above "
        f"and {lm['underpriced']} are below benchmark, with an average gap of {lm['avg_gap_pct']:+.1f}%."
        f"{prod_text} Price gaps are decision signals, not automatic price-change instructions."
    )


def generate_verified_weekly_brief(obs: pd.DataFrame, week: pd.Timestamp) -> str:
    w = obs[obs["week_start"] == pd.Timestamp(week)].copy()
    if w.empty:
        return "No observations are available for the selected week."

    m = summary_metrics(w)
    cat = category_summary(w)
    over = w.sort_values("price_gap_pct", ascending=False).head(3)
    under = w.sort_values("price_gap_pct", ascending=True).head(3)

    cat_sentence = ""
    if not cat.empty:
        top_cat = cat.iloc[0]
        low_cat = cat.iloc[-1]
        cat_sentence = (
            f"{top_cat['category']} had the highest average gap ({top_cat['avg_gap_pct']:+.1f}%), "
            f"while {low_cat['category']} had the lowest ({low_cat['avg_gap_pct']:+.1f}%)."
        )

    over_text = "; ".join(
        f"{r.product} ({r.price_gap_pct:+.1f}%)" for r in over.itertuples()
    )
    under_text = "; ".join(
        f"{r.product} ({r.price_gap_pct:+.1f}%)" for r in under.itertuples()
    )

    recommendation_parts: List[str] = []
    for r in over.itertuples():
        if r.price_gap_pct >= 5:
            recommendation_parts.append(
                f"review {r.product} because Our Brand is {r.price_gap_pct:.1f}% above the three-competitor average"
            )
    for r in under.itertuples():
        if r.price_gap_pct <= -8:
            recommendation_parts.append(
                f"check margin headroom on {r.product} because Our Brand is {abs(r.price_gap_pct):.1f}% below the benchmark"
            )
    if not recommendation_parts:
        recommendation_parts.append(
            "prioritise the largest absolute gaps and validate platform, availability, promotions and margin before changing price"
        )

    return (
        f"WEEKLY COMPETITOR PRICE INTELLIGENCE BRIEF — {pd.Timestamp(week):%d %B %Y}\n\n"
        f"Executive Summary\n"
        f"The tracker contains {m['observations']} comparable observations for the week. "
        f"Our Brand is above the three-competitor average in {m['overpriced']} observation(s) and below it in "
        f"{m['underpriced']} observation(s). The average normalized price gap is {m['avg_gap_pct']:+.1f}% "
        f"and the median is {m['median_gap_pct']:+.1f}%. Same-platform competitor coverage is "
        f"{m['same_platform_coverage_pct']:.0f}%.\n\n"
        f"Category Signal\n{cat_sentence}\n\n"
        f"Key Risks\nLargest positive gaps: {over_text}.\n\n"
        f"Opportunities\nLargest negative gaps: {under_text}.\n\n"
        f"Recommended Actions\n" + "; ".join(recommendation_parts) + ". "
        f"Before any price change, confirm stock status, platform comparability, promotion status and margin."
    )


def build_llm_prompt(obs: pd.DataFrame, week: pd.Timestamp) -> str:
    w = obs[obs["week_start"] == pd.Timestamp(week)].copy()
    if w.empty:
        return "No data for selected week."
    m = summary_metrics(w)
    cat = category_summary(w)[
        ["category", "observations", "avg_gap_pct", "overpriced", "underpriced"]
    ]
    rows = w[
        [
            "product",
            "category",
            "our_platform",
            "our_price_inr",
            "competitor_avg_price_inr",
            "price_gap_inr",
            "price_gap_pct",
            "our_availability",
            "same_platform_competitor_count",
            "same_platform_gap_pct",
        ]
    ].sort_values("price_gap_pct", ascending=False)

    return f"""You are a pricing analyst. Write a concise weekly competitor price-intelligence brief for management.

RULES:
1. Use ONLY the verified numbers below. Do not invent any figure.
2. Benchmark = Our Brand selling price versus the arithmetic mean of Competitor A, B and C for the same observation.
3. Positive price_gap_pct means Our Brand is more expensive; negative means cheaper.
4. Distinguish observed facts from recommendations.
5. Mention this limitation: same-platform competitor coverage is {m['same_platform_coverage_pct']:.1f}% and availability can differ.
6. Keep the brief under 300 words with four headings: Executive Summary, Key Risks, Opportunities, Recommended Actions.
7. Every numeric claim must be traceable to the supplied tables.
8. Do not recommend an automatic price change. State what should be validated before action.

WEEK: {pd.Timestamp(week):%Y-%m-%d}
OBSERVATIONS: {m['observations']}
OVERPRICED: {m['overpriced']}
UNDERPRICED: {m['underpriced']}
AVERAGE GAP %: {m['avg_gap_pct']:.2f}
MEDIAN GAP %: {m['median_gap_pct']:.2f}

CATEGORY SUMMARY:
{cat.to_csv(index=False)}

OBSERVATION DETAIL:
{rows.to_csv(index=False)}
"""


def recommendation_table(obs: pd.DataFrame, threshold_pct: float = 5.0) -> pd.DataFrame:
    if obs.empty:
        return pd.DataFrame()
    out = obs.copy()
    out["abs_gap_pct"] = out["price_gap_pct"].abs()
    high_cutoff = max(10.0, threshold_pct * 1.5)

    out["priority"] = np.select(
        [out["abs_gap_pct"] >= high_cutoff, out["abs_gap_pct"] >= threshold_pct],
        ["High", "Medium"],
        default="Low",
    )

    def action(row) -> str:
        if row["price_gap_pct"] >= threshold_pct:
            return "Review price/promotion or document why the premium is justified."
        if row["price_gap_pct"] <= -threshold_pct:
            return "Review margin opportunity; keep discount if it is strategically intentional."
        return "Monitor; gap is within the review threshold."

    out["recommended_action"] = out.apply(action, axis=1)
    out["evidence_note"] = np.where(
        out["same_platform_competitor_count"] > 0,
        "Same-platform competitor evidence available",
        "Cross-platform benchmark only",
    )
    rank = {"High": 0, "Medium": 1, "Low": 2}
    out["_priority_rank"] = out["priority"].map(rank)

    cols = [
        "week_start",
        "category",
        "product",
        "our_platform",
        "our_price_inr",
        "competitor_avg_price_inr",
        "price_gap_inr",
        "price_gap_pct",
        "position",
        "our_availability",
        "same_platform_competitor_count",
        "same_platform_gap_pct",
        "priority",
        "evidence_note",
        "recommended_action",
    ]
    return (
        out.sort_values(["_priority_rank", "abs_gap_pct"], ascending=[True, False])[cols]
        .reset_index(drop=True)
    )


def verification_checks(raw_df: pd.DataFrame, normalized_df: pd.DataFrame, obs: pd.DataFrame) -> pd.DataFrame:
    checks: List[Dict[str, str]] = []

    def add(name: str, passed: bool, detail: str):
        checks.append({"check": name, "status": "PASS" if passed else "REVIEW", "detail": detail})

    add("Source row count", len(raw_df) == 400, f"Found {len(raw_df)} rows; task brief says 400.")
    add("Complete observations", len(obs) == 100, f"Built {len(obs)} complete Our Brand + 3 competitor observations.")
    add(
        "Expected seller set",
        set(raw_df["seller"].astype(str).unique()) == EXPECTED_SELLERS,
        f"Sellers: {sorted(raw_df['seller'].astype(str).unique())}",
    )
    missing_price_count = pd.to_numeric(raw_df["selling_price_inr"], errors="coerce").isna().sum()
    add("No missing selling prices", missing_price_count == 0, f"Missing/non-numeric: {missing_price_count}")

    if not obs.empty:
        recomputed_avg = obs[[
            "competitor_a_price_inr",
            "competitor_b_price_inr",
            "competitor_c_price_inr",
        ]].mean(axis=1)
        add(
            "Three-competitor benchmark",
            bool(np.allclose(recomputed_avg, obs["competitor_avg_price_inr"], equal_nan=True)),
            "Benchmark equals mean(Competitor A, B, C) for every observation.",
        )
        recomputed_gap = obs["our_price_inr"] - obs["competitor_avg_price_inr"]
        add(
            "Gap formula",
            bool(np.allclose(recomputed_gap, obs["price_gap_inr"], equal_nan=True)),
            "price_gap_inr = our_price_inr - competitor_avg_price_inr for every observation.",
        )
        recomputed_pct = recomputed_gap / obs["competitor_avg_price_inr"] * 100
        add(
            "Gap % formula",
            bool(np.allclose(recomputed_pct, obs["price_gap_pct"], equal_nan=True)),
            "price_gap_pct = price_gap_inr / competitor_avg_price_inr × 100.",
        )
        add(
            "Three competitors per observation",
            bool(obs["source_rows_competitors"].str.split(",").str.len().eq(3).all()),
            "Each observation is traceable to exactly three competitor source rows.",
        )
        add(
            "Same-platform logic",
            bool(obs["same_platform_competitor_count"].between(0, 3).all()),
            "Same-platform count is restricted to 0–3 competitors.",
        )

    return pd.DataFrame(checks)


def ai_prompt_templates() -> pd.DataFrame:
    """Fifteen genuine prompt templates mapped to a defensible iterative workflow."""
    rows = [
        (1, "Understand data", "Inspect the supplied Price Tracker structure. Explain the grain of the data, the seller pattern, and what must be matched before any price comparison. Do not calculate yet."),
        (2, "Define methodology", "Propose a transparent formula for comparing Our Brand with Competitor A, B and C for the same observation. Explain why the three-competitor arithmetic mean is appropriate for this assignment and list limitations."),
        (3, "Validate pairing", "Given that product/week combinations can repeat, explain a safe way to preserve separate observations instead of collapsing them during grouping."),
        (4, "Check formulas", "Review these formulas: competitor benchmark = mean(A,B,C); gap = Our Price - benchmark; gap % = gap/benchmark*100. Identify sign interpretation and edge cases."),
        (5, "Category analysis", "Using only the verified category summary I provide, identify the categories with the highest and lowest average price gaps. Separate facts from recommendations."),
        (6, "Platform analysis", "Interpret the Our Brand platform summary. Explain why platform-level results are descriptive and why same-platform competitor coverage should be reported separately."),
        (7, "Product risks", "Using the verified product summary, identify persistent premium signals. Prioritise repeated observations over one-off extremes and do not invent causes."),
        (8, "Product opportunities", "Using the verified product summary, identify persistent discount signals that may indicate margin headroom. State what must be checked before recommending a price increase."),
        (9, "Latest-week brief", "Write a weekly competitor price-intelligence brief using only the verified metrics and rows supplied. Use Executive Summary, Key Risks, Opportunities and Recommended Actions."),
        (10, "Critique brief", "Critique the draft brief for unsupported causal claims, invented numbers, overconfident recommendations and missing data limitations. List specific corrections."),
        (11, "Rewrite brief", "Rewrite the brief after the critique. Keep every numeric claim traceable to the verified tables and distinguish observed facts from decision recommendations."),
        (12, "Recommendation logic", "Design a simple review rule using absolute price-gap thresholds. Explain why it should trigger human review rather than automatic price changes."),
        (13, "Verification plan", "Create a verification checklist for this pricing analysis: source-row traceability, three-competitor benchmark, gap formula, gap-percent formula and same-platform logic."),
        (14, "Management summary", "Convert the verified analysis into a concise management summary with no more than five actionable points. Mention platform, availability, promotions and margin as validation checks."),
        (15, "Viva preparation", "Act as my faculty evaluator. Ask me ten difficult viva questions about the methodology, coding, AI usage, verification, business recommendations and limitations, then provide concise model answers."),
    ]
    return pd.DataFrame(rows, columns=["entry", "stage", "prompt"])


def make_export_workbook(
    raw_df: pd.DataFrame,
    obs: pd.DataFrame,
    threshold_pct: float = 5.0,
    selected_week: Optional[pd.Timestamp] = None,
    ai_log_df: Optional[pd.DataFrame] = None,
) -> bytes:
    """Create a polished multi-sheet Excel analysis package in memory."""
    if selected_week is None and not obs.empty:
        selected_week = obs["week_start"].max()

    weekly = (
        obs[obs["week_start"] == selected_week].copy()
        if selected_week is not None
        else pd.DataFrame()
    )
    brief = generate_verified_weekly_brief(obs, selected_week) if selected_week is not None else ""
    ver = verification_checks(raw_df, _add_occurrence_index(raw_df), obs)
    rec = recommendation_table(obs, threshold_pct)
    actions = persistent_action_table(obs, threshold_pct)
    trend = weekly_trend(obs)
    prompts = ai_prompt_templates()

    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter", datetime_format="yyyy-mm-dd") as writer:
        sheets = {
            "Original Price Tracker": raw_df,
            "Price Gap Analysis": obs,
            "Category Summary": category_summary(obs),
            "Platform Summary": platform_summary(obs),
            "Product Summary": product_summary(obs),
            "Weekly Trend": trend,
            "Selected Week": weekly,
            "Action Centre": actions,
            "Recommendations": rec,
            "Verification": ver,
            "AI Prompt Pack": prompts,
        }
        if ai_log_df is not None and not ai_log_df.empty:
            sheets["AI Use Log"] = ai_log_df

        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name[:31], index=False)

        pd.DataFrame({"weekly_brief": brief.splitlines()}).to_excel(
            writer, sheet_name="Weekly Brief", index=False
        )

        workbook = writer.book
        header_fmt = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#17324D",
                "font_color": "#FFFFFF",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )
        money_fmt = workbook.add_format({"num_format": '₹#,##0.00'})
        pct_num_fmt = workbook.add_format({"num_format": '0.0"%"'})
        date_fmt = workbook.add_format({"num_format": "yyyy-mm-dd"})
        wrap_fmt = workbook.add_format({"text_wrap": True, "valign": "top"})
        over_fmt = workbook.add_format({"bg_color": "#FDECEC", "font_color": "#9B1C1C"})
        under_fmt = workbook.add_format({"bg_color": "#EAF7EE", "font_color": "#166534"})

        for sheet_name, df_out in sheets.items():
            ws = writer.sheets[sheet_name[:31]]
            ws.freeze_panes(1, 0)
            if len(df_out.columns):
                ws.autofilter(0, 0, max(len(df_out), 1), len(df_out.columns) - 1)
            ws.set_row(0, 28)
            for c, col in enumerate(df_out.columns):
                ws.write(0, c, col, header_fmt)
                sample = df_out[col].astype(str).head(100) if len(df_out) else pd.Series(dtype=str)
                max_data = int(sample.map(len).max()) if not sample.empty else 0
                width = min(max(max_data + 2, len(str(col)) + 2, 12), 42)
                ws.set_column(c, c, width)

                lc = str(col).lower()
                if lc.endswith("_inr") or "price_inr" in lc or "gap_inr" in lc:
                    ws.set_column(c, c, width, money_fmt)
                elif lc.endswith("_pct") or "coverage_pct" in lc:
                    ws.set_column(c, c, width, pct_num_fmt)
                elif "week" in lc and pd.api.types.is_datetime64_any_dtype(df_out[col]):
                    ws.set_column(c, c, max(width, 13), date_fmt)
                elif "action" in lc or "detail" in lc or "prompt" in lc:
                    ws.set_column(c, c, min(max(width, 28), 55), wrap_fmt)

            if "price_gap_pct" in df_out.columns and len(df_out):
                c = df_out.columns.get_loc("price_gap_pct")
                ws.conditional_format(1, c, len(df_out), c, {
                    "type": "cell", "criteria": ">", "value": 0, "format": over_fmt
                })
                ws.conditional_format(1, c, len(df_out), c, {
                    "type": "cell", "criteria": "<", "value": 0, "format": under_fmt
                })

        brief_ws = writer.sheets["Weekly Brief"]
        brief_ws.set_column(0, 0, 110, wrap_fmt)
        brief_ws.freeze_panes(1, 0)

    bio.seek(0)
    return bio.getvalue()
