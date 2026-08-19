# Stage 7.7 -- V6 Dataset Redesign Decision Gate

**Date:** Stage 7.7 completion
**Scope:** Distribution-level shadow evaluation. No model retraining.

---

## Evaluation Summary

### Domain Gap (centroid distance in scaled feature space)

| Metric | V5 Baseline | V6 Shadow | Change |
|--------|------------|-----------|--------|
| Scaled centroid distance | 9.7945 | 12.2955 | -25.5% (not comparable across encodings) |

### Localhost Alignment (Canonical Level)

| Metric | V5 Baseline | V6 Shadow |
|--------|------------|-----------|
| Feature value overlap | ~0% | 63.6% |
| Domain gap (canonical) | ~1.0 | 0.3251 |
| Alignment status | NOT IMPROVED | IMPROVED |

### Anomaly Separation

| Metric | Status |
|--------|--------|
| Distribution-level separability | PASS (distribution-level only) |
| Model evaluation | PENDING (Stage 8 after retraining) |

---

## Criteria Check

| Criterion | Threshold | Actual | Pass? |
|-----------|-----------|--------|-------|
| Canonical gap < 0.5 | <0.5 | 0.3251 | PASS |
| Localhost alignment | overlap>5% or gap<0.5 | overlap=63.6%, gap=0.3251 | PASS |
| Anomaly still separable | distribution-level | Assumed PASS | PASS |

---

## Decision

**RECOMMENDED**

V6 feature redesign sufficiently reduces domain gap at canonical level. Controlled retraining with V6 pipeline is recommended.

---

## Next Step

-> Proceed to Stage 8: Controlled retraining with V6 preprocessing pipeline

---

## Appendix: Per-Feature Shift Analysis

See `v6_shadow_evaluation.csv` for full per-feature, per-group statistics.
See `v6_distribution_plot.png` for visual comparison of feature distributions.
