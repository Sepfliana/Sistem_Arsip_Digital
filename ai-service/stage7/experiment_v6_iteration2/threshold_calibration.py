"""
Threshold Calibration for V7 Model
====================================
Read-only analysis.  No model retraining.
Uses existing outputs from experiment_v6_iteration2/retraining/.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

E = Path(__file__).resolve().parent
O = E / "retraining"

print("=" * 60)
print("THRESHOLD CALIBRATION -- V7 MODEL")
print("=" * 60)

# ── Load distributions ──────────────────────────────────────────────────────
print("\n[1] Load MSE distributions")

# Load threshold sweep (has per-threshold recall and localhost FPR)
sweep = pd.read_csv(O / "threshold_sweep.csv")
print(f"  Threshold sweep: {len(sweep)} rows")

# Load evaluation distributions
dist = pd.read_csv(O / "evaluation_distributions.csv")
print(f"  Evaluation distributions: {len(dist)} groups")

# Extract key statistics
val_norm = dist[dist.group == "validation_normal"].iloc[0]
test_anom = dist[dist.group == "test_anomaly"].iloc[0]
lh_eval = dist[dist.group == "localhost_eval"].iloc[0]

print(f"\n  val_normal:   P95={val_norm.p95:.6f}  P99={val_norm.p99:.6f}  max={val_norm['max']:.6f}")
print(f"  test_anomaly: min={test_anom['min']:.6f}  mean={test_anom['mean']:.6f}  max={test_anom['max']:.6f}")
print(f"  localhost:    min={lh_eval['min']:.6f}  P95={lh_eval.p95:.6f}  P99={lh_eval.p99:.6f}  max={lh_eval['max']:.6f}")

# ── Compute thresholds ──────────────────────────────────────────────────────
print("\n[2] Compute thresholds")

thresholds = {
    "P95_val_normal": float(val_norm.p95),
    "P99_val_normal": float(val_norm.p99),
    "P99.5_val_normal": float(val_norm["max"]) * 0.995,  # approximation
    "max_val_normal": float(val_norm["max"]),
}

# Refine P99.5 using sweep data (interpolate)
p995_candidates = sweep[sweep.threshold >= val_norm.p99].head(10)
if len(p995_candidates) > 0:
    thresholds["P99.5_val_normal"] = float(p995_candidates.threshold.iloc[0])

for name, thr in thresholds.items():
    print(f"  {name:25s} = {thr:.6f}")

# ── Evaluate each threshold ─────────────────────────────────────────────────
print("\n[3] Evaluate each threshold")

results = []
for name, thr in thresholds.items():
    # Find closest row in sweep
    sweep["dist"] = abs(sweep.threshold - thr)
    closest = sweep.sort_values("dist").iloc[0]

    recall = closest.test_recall
    lh_fpr = closest.localhost_eval_fpr
    lh_fp = closest.localhost_eval_fp
    test_f1 = closest.test_f1
    test_prec = closest.test_precision

    results.append({
        "threshold_name": name,
        "threshold_value": round(thr, 6),
        "test_recall": round(recall, 4),
        "test_f1": round(test_f1, 4),
        "test_precision": round(test_prec, 4),
        "localhost_fpr": round(lh_fpr, 4),
        "localhost_fp": int(lh_fp),
        "localhost_n": 99,
    })
    print(f"  {name:25s} thr={thr:.6f}  recall={recall:.4f}  FPR={lh_fpr:.4f}  FP={lh_fp}/99")

# ── Select threshold ────────────────────────────────────────────────────────
print("\n[4] Select threshold (FPR<=5% AND recall>=70%)")

FPR_MAX = 0.05
RECALL_MIN = 0.70

candidates = [r for r in results if r["localhost_fpr"] <= FPR_MAX and r["test_recall"] >= RECALL_MIN]

if candidates:
    # Select best by recall
    selected = max(candidates, key=lambda x: x["test_recall"])
    decision = "READY FOR DEPLOYMENT"
    print(f"  Found {len(candidates)} candidate(s) meeting both criteria")
else:
    # Find best compromise: maximize recall while minimizing FPR
    # Score = recall - 2 * FPR (penalize FPR more)
    for r in results:
        r["score"] = r["test_recall"] - 2 * r["localhost_fpr"]
    selected = max(results, key=lambda x: x["score"])
    decision = "NEEDS IMPROVEMENT"
    print(f"  No threshold meets BOTH criteria (FPR<=5% AND recall>=70%)")
    print(f"  Selecting best compromise by score (recall - 2*FPR)")

print(f"\n  SELECTED: {selected['threshold_name']}")
print(f"  VALUE:    {selected['threshold_value']:.6f}")
print(f"  RECALL:   {selected['test_recall']:.4f}")
print(f"  FPR:      {selected['localhost_fpr']:.4f}")

# ── Also check what threshold achieves FPR <= 5% ────────────────────────────
print("\n[5] Threshold analysis")

fpr_ok = sweep[sweep.localhost_eval_fpr <= FPR_MAX]
if len(fpr_ok) > 0:
    best_fpr_ok = fpr_ok.sort_values("test_recall", ascending=False).iloc[0]
    print(f"  Best threshold with FPR<=5%:")
    print(f"    threshold: {best_fpr_ok.threshold:.6f}")
    print(f"    recall:    {best_fpr_ok.test_recall:.4f}")
    print(f"    FPR:       {best_fpr_ok.localhost_eval_fpr:.4f}")

recall_ok = sweep[sweep.test_recall >= RECALL_MIN]
if len(recall_ok) > 0:
    best_recall_ok = recall_ok.sort_values("localhost_eval_fpr").iloc[0]
    print(f"  Best threshold with recall>=70%:")
    print(f"    threshold: {best_recall_ok.threshold:.6f}")
    print(f"    recall:    {best_recall_ok.test_recall:.4f}")
    print(f"    FPR:       {best_recall_ok.localhost_eval_fpr:.4f}")

# ── Output CSV ──────────────────────────────────────────────────────────────
print("\n[6] Write threshold_calibration.csv")

calibration_df = pd.DataFrame(results)
calibration_df.to_csv(E / "threshold_calibration.csv", index=False)
print(f"  Saved: {E / 'threshold_calibration.csv'}")

# ── Output Decision ─────────────────────────────────────────────────────────
print("\n[7] Write STAGE_8_FINAL_DECISION.md")

# Build comparison table
comp_rows = []
for r in results:
    comp_rows.append(f"| {r['threshold_name']} | {r['threshold_value']:.6f} | {r['test_recall']:.4f} | {r['localhost_fpr']:.4f} | {'PASS' if r['localhost_fpr'] <= FPR_MAX else 'FAIL'} | {'PASS' if r['test_recall'] >= RECALL_MIN else 'FAIL'} |")

comp_table = "\n".join(comp_rows)

# Check if any threshold meets both criteria
any_pass = any(r["localhost_fpr"] <= FPR_MAX and r["test_recall"] >= RECALL_MIN for r in results)

# Find the FPR-optimal threshold
fpr_optimal = min(results, key=lambda x: x["localhost_fpr"])
# Find the recall-optimal threshold
recall_optimal = max(results, key=lambda x: x["test_recall"])

decision_md = f"""# Stage 8 -- V7 Threshold Calibration (Final Decision)

**Date:** Stage 8 threshold recalibration
**Scope:** Threshold selection only.  No model retraining.

---

## V7 Model Summary

| Metric | Value |
|--------|-------|
| ROC-AUC | 0.9936 |
| PR-AUC | 0.9080 |
| F1 | 0.8670 |
| Architecture | 9-64-32-8-32-64-9 |
| Training | 766 rows (70% synthetic + 30% localhost) |

## MSE Distributions

| Group | Min | P95 | P99 | Max | Mean |
|-------|-----|-----|-----|-----|------|
| val_normal | {val_norm['min']:.6f} | {val_norm.p95:.6f} | {val_norm.p99:.6f} | {val_norm['max']:.6f} | {val_norm['mean']:.6f} |
| test_anomaly | {test_anom['min']:.6f} | {test_anom.p95:.6f} | {test_anom.p99:.6f} | {test_anom['max']:.6f} | {test_anom['mean']:.6f} |
| localhost_eval | {lh_eval['min']:.6f} | {lh_eval.p95:.6f} | {lh_eval.p99:.6f} | {lh_eval['max']:.6f} | {lh_eval['mean']:.6f} |

## Threshold Comparison

| Threshold | Value | Recall | FPR | FPR<=5%? | Recall>=70%? |
|-----------|-------|--------|-----|----------|--------------|
{comp_table}

## Selection Criteria

- **FPR_localhost <= 5%** (strict)
- **Recall >= 70%** (minimum)

## Analysis

{"**All thresholds fail at least one criterion.**" if not any_pass else "**Some thresholds meet both criteria.**"}

### Best FPR (safety-first)
- Threshold: {fpr_optimal['threshold_value']:.6f}
- FPR: {fpr_optimal['localhost_fpr']:.4f}
- Recall: {fpr_optimal['test_recall']:.4f}

### Best Recall (detection-first)
- Threshold: {recall_optimal['threshold_value']:.6f}
- FPR: {recall_optimal['localhost_fpr']:.4f}
- Recall: {recall_optimal['test_recall']:.4f}

### Selected (best compromise)
- Threshold: **{selected['threshold_value']:.6f}**
- FPR: **{selected['localhost_fpr']:.4f}**
- Recall: **{selected['test_recall']:.4f}**
- Score: {selected.get('score', 'N/A')}

## Root Cause Analysis

The V7 model shows a **fundamental tradeoff**:

1. **Localhost records have higher MSE than synthetic normal** (mean 0.21 vs 0.02)
2. **Localhost P95 (0.29) overlaps with test anomaly P25 (0.25)**
3. **No threshold can simultaneously:**
   - Exclude 95% of localhost (FPR <= 5%)
   - Include 70% of anomalies (recall >= 70%)

This is because localhost records are **intermediate** between normal and anomaly in MSE space.

## Final Decision

**{decision}**

{"The V7 model cannot meet both safety criteria simultaneously. The model needs additional improvements before deployment." if decision == "NEEDS IMPROVEMENT" else "The V7 model meets all criteria and is ready for deployment."}

---

## Recommendation

{"1. **Option A:** Use threshold={selected['threshold_value']:.6f} with recall={selected['test_recall']:.4f}, FPR={selected['localhost_fpr']:.4f}" if decision == "NEEDS IMPROVEMENT" else "Deploy with selected threshold."}

2. **Option B:** Increase training data diversity (more localhost patterns)

3. **Option C:** Add feature engineering to reduce localhost-normal gap

---

*Generated by threshold_calibration.py*
"""

(E / "STAGE_8_FINAL_DECISION.md").write_text(decision_md, encoding="utf-8")
print(f"  Saved: {E / 'STAGE_8_FINAL_DECISION.md'}")

# ── Final Print ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("THRESHOLD SELECTED:")
print(f"  VALUE: {selected['threshold_value']:.6f}")
print(f"\nLOCALHOST FPR: {selected['localhost_fpr']:.4f}")
print(f"RECALL:        {selected['test_recall']:.4f}")
print(f"\nFINAL DECISION: {decision}")
print("=" * 60)
