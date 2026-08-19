# Stage 7.6 — Final Decision Gate

**Date:** Stage 7.6 completion
**Scope:** Read-only forensic analysis + experiment design. No implementation.
**Decision authority:** This document determines whether Stage 8 can proceed.

---

## Decision Questions

### Q1: Is domain shift fixable WITHOUT retraining?

**ANSWER: NO (with one exception)**

**Reasoning:**
- The dominant MSE contributors (`ip_address` 301%, `duration_ms` 532%) are **structurally incompatible** with the current model. No preprocessing trick can make the V5 model reconstruct unseen `ip_address` categories or zero `duration_ms` values.
- The **one exception** is `device`: mapping "Unknown Device" → "PC Windows" is a preprocessing-only fix that requires no retraining. However, this eliminates only 14.4% of localhost MSE — insufficient to bring FPR below 5%.
- All other fixes (ip_address redesign, duration_ms binary, hour binning, activity vocabulary) change the feature encoding, which requires retraining the model on the new encoding.

**Evidence:**
- Current localhost min MSE (2.35) >> V5 train max MSE (0.26) — gap = 2.09
- MSE distributions are completely disjoint — no threshold can bridge this gap
- Only device fix (14.4% of MSE) is preprocessing-compatible

---

### Q2: Is feature redesign REQUIRED?

**ANSWER: YES**

**Reasoning:**
The root causes are structural, not parametric:

| Feature | Root Cause | Why redesign is required |
|---------|-----------|------------------------|
| `ip_address` | Constant in training (std=0), unseen category in localhost | Current encoding creates ∞ divergence; must redesign to binary Internal/External |
| `duration_ms` | Systematic zero in localhost (no telemetry) | Current continuous encoding creates 8.83σ shift; must redesign to binary flag |
| `hour` | Uniform vs concentrated distribution | Continuous encoding amplifies shift; 4-period binning reduces gap |
| `activity` | 3 unseen categories | Vocabulary expansion needed to include all localhost activities |
| `device` | Unseen "Unknown Device" category | Fallback mapping eliminates mismatch |

**No alternative exists:** Threshold tuning, reweighting, or distribution alignment cannot fix these issues because:
- `ip_address` has zero variance in training — any alignment is meaningless
- `duration_ms` has a systematic zero — no reweighting can create non-zero values
- The MSE gap (2.09) exceeds any realistic threshold range

---

### Q3: Is new dataset (V6) REQUIRED?

**ANSWER: YES**

**Reasoning:**
- V5 dataset uses the old preprocessing pipeline (6-category ip_address, continuous duration_ms, 24h hour, 12-category activity)
- V6 requires reprocessed training data with redesigned features
- The same 8750 raw TRAIN_NORMAL records are used; only the canonical encoding changes
- This is **not** a new data collection — it is reprocessing through a new pipeline

**Scope of change:**
- `preprocessing_contract.py` updated with new functions
- `process_record()` output changed (same 9 features, different encoding)
- `label_encoders_v6.pkl` trained on new canonical categories
- `scaler_v6.pkl` fit on V6 train normal data

---

### Q4: Is model architecture change REQUIRED?

**ANSWER: NO**

**Reasoning:**
- All 5 proposed fixes preserve the 9-feature input dimension
- The VAE architecture (9→64→32→[mu=8,logvar=8]→8→32→64→9) is unchanged
- Only preprocessing changes; model capacity and structure remain the same
- No new layers, no new hyperparameters, no new loss terms

---

### Q5: Can Stage 8 proceed?

**ANSWER: NOT YET — Stage 7.6 → Stage 8 gate is CONDITIONAL**

**Prerequisites for Stage 8:**

| Prerequisite | Status | Blocking? |
|-------------|--------|-----------|
| Forensic root cause identified | COMPLETE | No |
| Solution strategy designed | COMPLETE | No |
| Shadow experiment designed | COMPLETE | No |
| Shadow experiment executed | **NOT DONE** | **YES** |
| Variant passes acceptance criteria | **NOT DONE** | **YES** |
| V6 model validated | **NOT DONE** | **YES** |

**Stage 8 can proceed ONLY AFTER:**
1. Shadow experiment (Variant B or C) is executed
2. FPR_localhost_val ≤ 5%
3. ROC_AUC_test ≥ 0.995
4. F1_test ≥ 0.990
5. Recall_test_anomaly ≥ 0.990

---

## Recommended Path Forward

```
Stage 7.6 (COMPLETE)
    │
    ├── device fix (no retraining) → immediate deployment
    │       └── reduces FPR by ~14.4% → not sufficient alone
    │
    └── V6 shadow experiment (retraining required)
            │
            ├── Variant C (ip_address + duration_ms only)
            │       └── test if CRITICAL fixes are sufficient
            │
            └── Variant B (full redesign)
                    └── test if complete fix achieves near-zero FPR
                            │
                            └── if passes → Stage 8
```

**Immediate action:** Deploy `device` fallback fix (no risk, no retraining).
**Next action:** Execute shadow experiment Variant C or B.
**Final gate:** Stage 8 proceeds only after experiment passes acceptance criteria.

---

## Deliverables Summary

| File | Purpose | Status |
|------|---------|--------|
| `domain_gap_ranking.csv` | Per-feature severity ranking with scores | COMPLETE |
| `domain_gap_root_causes.json` | Root cause classification (A/B/C/D) per feature | COMPLETE |
| `domain_gap_solution_plan.md` | Fix strategy for each CRITICAL/HIGH feature | COMPLETE |
| `shadow_experiment_plan.md` | Experiment design with metrics and acceptance criteria | COMPLETE |
| `STAGE_7_6_DECISION.md` | This document — final decision gate | COMPLETE |

---

## Appendices

### Appendix A: Domain Gap Scores

| Rank | Feature | Severity | Score | Root Cause | Fix Type |
|------|---------|----------|-------|-----------|----------|
| 1 | ip_address | CRITICAL | 100.0 | AD | Feature redesign (6→2 categories) |
| 2 | duration_ms | CRITICAL | 95.4 | CB | Feature redesign (continuous→binary) |
| 3 | hour | HIGH | 75.9 | B | Feature redesign (24h→4-period) |
| 4 | device | HIGH | 66.7 | C | Fallback mapping (no retraining) |
| 5 | user_id | HIGH | 52.9 | B | Defer (lower priority) |
| 6 | activity | MEDIUM | 43.7 | C | Vocabulary reduction (12→8) |
| 7 | day_of_week | MEDIUM | 31.0 | B | Defer (low contribution) |
| 8 | object_count | MEDIUM | 28.7 | B | Defer (low contribution) |
| 9 | status | MEDIUM | 23.0 | C | Defer (negligible contribution) |

### Appendix B: Key Forensic Evidence

- **MSE gap:** localhost min (2.35) >> train max (0.26) — gap = 2.09
- **KL ratio:** localhost/train = 2.80×
- **Latent distance:** localhost centroid 8.01 from train (2.89× anomaly distance)
- **Zero overlap:** No threshold can separate train normal from localhost

### Appendix C: Evidence Sources

All forensic CSVs in `stage7/experiment_v5/forensic/`:
- `per_feature_mse_decomposition.csv`
- `kl_divergence_analysis.csv`
- `latent_space_analysis.csv`
- `latent_mu_dimension_comparison.csv`
- `scaled_feature_comparison.csv`
- `domain_gap_ranking.csv`
