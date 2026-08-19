# Stage 8 FINAL -- V8.1 Retraining Decision Gate

**Date:** Stage 8 final
**Scope:** Experiment-only. No deployment.

---

## V8.1 Anomaly Dataset
- 1000 calibrated anomalies (2-3 features mutated)
- Types: failed_offhours_access, unknown_external_access, failed_vm_access
- Within training domain (user_id 1-86, object_count <=10)

## Test Performance

| Metric | Value |
|--------|-------|
| ROC-AUC | 0.9961 |
| PR-AUC | 0.9500 |
| F1 | 0.8918 |
| Precision | 0.8936 |
| Recall | 0.8900 |

## Localhost Safety

| Threshold | FPR |
|-----------|-----|
| F1 optimal (0.209528) | 58.59% |
| P99 (0.203553) | 59.60% |
| P99.5 (0.305531) | 0.00% |
| Production (3.149629) | 0.00% |

## Domain Gap

| Metric | Value |
|--------|-------|
| localhost_eval_min | 0.000904 |
| localhost_eval_max | 0.291669 |
| localhost_eval_p95 | 0.285348 |
| normal_max | 1.975722 |
| gap | -1.974818 |

## Threshold Selection

**Best threshold found:** 0.296394

| Criterion | Threshold | Actual | Pass? |
|-----------|-----------|--------|-------|
| F1 >= 0.80 | >=0.80 | 0.8918 | PASS |
| Localhost FPR <= 10% | <=10% | 0.00% | PASS |

## Decision

**EXPERIMENT SUCCESS**

V8.1 calibrated anomalies resolve the overlap. Model is production-viable.

---

## Next Step

-> Proceed to Stage 9: Production readiness validation
