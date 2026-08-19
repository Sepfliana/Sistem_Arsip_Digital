# Stage 8 -- V7 Retraining Decision Gate

**Date:** Stage 8 iteration 2
**Scope:** Experiment-only retraining. No deployment.

---

## V7 Fixes Applied
1. Status preprocessing: unseen status -> 'Berhasil' (mode of train_normal)
2. Training data: 70% synthetic + 30% localhost (no leakage)

## Test Performance

| Metric | V6 | V7 |
|--------|-----|-----|
| ROC-AUC | 1.0000 | 0.9936 |
| PR-AUC | 0.9999 | 0.9080 |
| F1 | 0.9990 | 0.8670 |
| Precision | 0.998 | 0.8104 |
| Recall | 1.000 | 0.9320 |

## Localhost Safety (eval only)

| Threshold | FPR |
|-----------|-----|
| F1 optimal (0.203241) | 70.71% |
| P99 (0.285894) | 22.22% |
| Production (3.149629) | 0.00% |

## Domain Gap

| Metric | V6 | V7 |
|--------|-----|-----|
| localhost_eval_min_mse | 2.1829 | 0.002320 |
| localhost_eval_max_mse | 2.856 | 0.345284 |
| normal_max_mse | 0.1883 | 1.574630 |
| gap | 1.9946 | -1.572309 |

## Criteria

| Criterion | Threshold | Actual | Pass? |
|-----------|-----------|--------|-------|
| F1 >= 0.80 | >=0.80 | 0.8670 | PASS |
| Localhost FPR < 20% | <20% | 70.71% | FAIL |

## Decision

**EXPERIMENT FAIL**

V7 fixes did not fully resolve localhost FPR. Consider additional fixes.

---

## Next Step

-> Investigate remaining domain gap; consider additional preprocessing or architecture changes
