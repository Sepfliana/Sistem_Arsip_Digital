# Stage 8 -- V6 Retraining Decision Gate

**Date:** Stage 8 completion
**Scope:** Experiment-only retraining. No deployment.

---

## Test Performance

| Metric | V5 | V6 | Change |
|--------|-----|-----|--------|
| ROC-AUC | 0.9998 | 1.0000 | |
| PR-AUC | 0.9991 | 0.9999 | |
| F1 | 0.9960 | 0.9990 | |
| Precision | 0.996 | 0.9980 | |
| Recall | 0.996 | 1.0000 | |

## Localhost Safety

| Metric | V5 | V6 | Change |
|--------|-----|-----|--------|
| FPR (val threshold) | 100.00% | 100.00% | 0.00% reduction |
| FPR (safe P99) | -- | 100.00% | |
| FPR (production) | 41.6% | 0.00% | |

## Domain Gap

| Metric | V5 | V6 |
|--------|-----|-----|
| localhost_min_mse | 2.389 | 2.182856 |
| normal_max_mse | 0.183 | 0.188254 |
| gap | -2.206 | 1.994602 |

## Criteria

| Criterion | Threshold | Actual | Pass? |
|-----------|-----------|--------|-------|
| F1 > 0.8 | >0.8 | 0.9990 | PASS |
| Localhost FPR < 10% | <10% | 100.00% | FAIL |

## Decision

**EXPERIMENT FAIL**

V6 retraining did not fully resolve localhost FPR. Further investigation needed.

---

## Next Step

-> Investigate remaining domain gap; consider additional preprocessing or architecture changes
