from pathlib import Path
import numpy as np

from analysis_core import (
    build_observation_table,
    read_price_tracker,
    summary_metrics,
    verification_checks,
    make_export_workbook,
)

p = Path(__file__).with_name("T44_Competitor_price_intelligence_brief.xlsx")
raw = read_price_tracker(p)
obs, normalized = build_observation_table(raw)

assert len(raw) == 400, len(raw)
assert len(obs) == 100, len(obs)
assert np.allclose(
    obs[["competitor_a_price_inr", "competitor_b_price_inr", "competitor_c_price_inr"]].mean(axis=1),
    obs["competitor_avg_price_inr"],
)
assert np.allclose(
    obs["our_price_inr"] - obs["competitor_avg_price_inr"],
    obs["price_gap_inr"],
)
checks = verification_checks(raw, normalized, obs)
assert (checks["status"] == "PASS").all(), checks.to_string(index=False)
metrics = summary_metrics(obs)
assert metrics["overpriced"] + metrics["underpriced"] + metrics["at_benchmark"] == 100
blob = make_export_workbook(raw, obs)
assert len(blob) > 10_000
print("PASS: 400 rows -> 100 observations; formulas verified; Excel export generated.")
print(metrics)
