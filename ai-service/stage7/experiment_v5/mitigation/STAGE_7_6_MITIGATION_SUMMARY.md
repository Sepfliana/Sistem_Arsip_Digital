# Stage 7.6 — Final Mitigation Summary

**Date:** Post-mitigation analysis
**Scope:** Evidence-based evaluation of device fallback mitigation
**Source:** All artifacts in `stage7/experiment_v5/mitigation/`

---

## 1. Metrics BEFORE vs AFTER

| Metric | BEFORE (V5) | AFTER (device fix) | Delta | Delta % |
|--------|------------|-------------------|-------|---------|
| **test_normal** | | | | |
| Mean MSE | 0.007928 | 0.008015 | +0.000087 | +1.10% |
| P50 | 0.005172 | 0.005197 | +0.000025 | +0.48% |
| P95 | 0.021177 | 0.021101 | -0.000076 | -0.36% |
| P99 | 0.046857 | 0.046897 | +0.000040 | +0.09% |
| Max | 0.182613 | 0.166555 | -0.016058 | -8.79% |
| **validation_anomaly** | | | | |
| Mean MSE | 0.253908 | 0.234649 | -0.019259 | -7.58% |
| P50 | 0.215561 | 0.205854 | -0.009707 | -4.50% |
| P95 | 0.366381 | 0.307683 | -0.058698 | -16.02% |
| Recall (val thr) | 100.0% | 72.6% | -27.4pp | CRITICAL |
| **test_anomaly** | | | | |
| Mean MSE | 0.258337 | 0.228963 | -0.029374 | -11.37% |
| P50 | 0.229643 | 0.207030 | -0.022613 | -9.85% |
| P95 | 0.385166 | 0.306584 | -0.078582 | -20.40% |
| Recall (val thr) | 99.2% | 74.0% | -25.2pp | CRITICAL |
| **localhost** | | | | |
| Mean MSE | 2.987341 | 2.907050 | -0.080291 | -2.69% |
| P50 | 3.107576 | 3.029548 | -0.078028 | -2.51% |
| P95 | 3.284185 | 3.219326 | -0.064859 | -1.97% |
| P99 | 3.346205 | 3.284640 | -0.061565 | -1.84% |
| Max | 3.416126 | 3.316752 | -0.099374 | -2.91% |

**Critical observation:** Anomaly recall collapsed. Validation anomaly recall dropped from 100% to 72.6% — the device fallback is actively degrading anomaly detection.

---

## 2. Localhost Safety Check

| Threshold | BEFORE FPR | AFTER FPR | Records Changed | Status |
|-----------|-----------|----------|----------------|--------|
| Validation (0.13773) | 100.0% (329/329) | 100.0% (329/329) | 0 | **NO CHANGE** |
| Production (3.1496) | 40.4% (133/329) | 20.7% (68/329) | -65 | Improved |
| Normal max MSE | 100% | 100% | 0 | **NO CHANGE** |

**Overlap analysis:**

| Metric | BEFORE | AFTER | Change |
|--------|--------|-------|--------|
| test_normal max MSE | 0.182613 | 0.166555 | -8.8% |
| localhost min MSE | 2.389328 | 2.331849 | -2.4% |
| Gap (lh_min - tn_max) | 2.206715 | 2.165294 | -1.9% |

**Verdict:** Localhost is still FULLY REJECTED at validation threshold. The gap decreased by only 1.9% — negligible. Localhost min MSE (2.33) remains 14× larger than test normal max MSE (0.17). No threshold can bridge this gap.

---

## 3. Domain Gap Re-evaluation

| Metric | BEFORE | AFTER | Change |
|--------|--------|-------|--------|
| Localhost mean MSE | 2.987341 | 2.907050 | -2.69% |
| Train normal mean MSE | 0.007928 | 0.008015 | +1.10% |
| Ratio (lh / train) | 376.8× | 362.7× | -3.7% |
| Gap (lh_min - tn_max) | 2.207 | 2.165 | -1.9% |

**Classification: NO CHANGE**

The domain gap decreased by less than 3%. The MSE distributions remain completely disjoint with a gap of 2.17 (vs. 2.21 before). The device fallback did not meaningfully reduce the structural domain shift.

**Why:** Device contributes only 14.4% of total localhost MSE (0.431 out of 2.987). Even if device MSE were reduced to zero, the remaining 85.6% (ip_address=301%, duration_ms=532%, hour=29%, activity=13%) would still keep localhost far above threshold.

---

## 4. Device Fallback Effectiveness

| Question | Answer | Evidence |
|----------|--------|----------|
| Did device normalization reduce anomaly score? | YES (for anomalies) | Validation anomaly mean MSE: -7.6%, test anomaly: -11.4% |
| Did it reduce localhost MSE? | MINIMALLY | -2.69% (0.08 out of 2.987 total) |
| Did it improve localhost FPR at val threshold? | NO | 100% → 100% (0 records changed) |
| Did it improve overlap? | NO | Gap 2.21 → 2.17 (1.9% change) |
| Did it preserve anomaly detection? | **NO — CRITICAL FAILURE** | Validation recall: 100% → 72.6% (-27.4pp) |

**Conclusion: FAILED**

The device fallback has a paradoxical effect:
1. It REDUCES anomaly scores (good for FPR) but also REDUCES scores for anomalies (bad for recall)
2. The model was trained with specific device patterns. Remapping "Unknown Device" → "PC Windows" creates a mismatch the model didn't learn — "PC Windows" in training was always paired with specific IP/duration/hour patterns. Remapping device alone doesn't fix those other features.
3. The net effect is: anomalies look more like normals (recall drops), but localhost still looks nothing like normals (FPR unchanged).

---

## 5. FINAL DECISION

### **C) Mitigation FAILED → Dataset/domain redesign required (V6)**

**Rationale:**
1. Single-feature device fix achieves <3% reduction in localhost MSE — negligible
2. The fix actively degrades anomaly recall by 25-27 percentage points — unacceptable
3. The root cause (ip_address=301%, duration_ms=532% of MSE) is unaffected by device fix
4. No additional single-feature mitigation can fix the problem — multi-feature redesign is the only path

**The device fallback approach is counterproductive and must be REVERTED.** The original V5 preprocessing pipeline should be preserved.

---

## 6. NEXT STEP (Strict Roadmap)

**Trigger V6 Dataset Design + Shadow Experiment**

The following actions are required:

### Immediate (no retraining)
1. **REVERT device fallback** — do not deploy the "Unknown Device" → "PC Windows" mapping
2. **Document failure** — device-only fix is proven insufficient and harmful to recall

### V6 Dataset Design (pre-retraining)
3. Design V6 preprocessing pipeline with ALL CRITICAL + HIGH feature fixes:
   - `ip_address`: 6-category → binary Internal/External
   - `duration_ms`: continuous → binary has_telemetry flag
   - `hour`: 24h continuous → 4-period categorical
   - `device`: keep original (fallback fix is harmful)
   - `activity`: 12 → 8 categories (merge rare)

4. **Key constraint:** V6 must include localhost-like distribution in training data to prevent domain shift recurrence

5. Execute shadow experiment Variant B (full feature redesign) from `shadow_experiment_plan.md`

### Gate for Stage 8
Stage 8 proceeds ONLY after:
- V6 model achieves FPR_localhost ≤ 5% at validation threshold
- Anomaly recall ≥ 99% at validation threshold
- MSE gap (localhost_min - normal_max) > 0 (gap preserved)

---

## Appendix: Raw Data Sources

| File | Content |
|------|---------|
| `mitigation/mse_after_device_fallback.csv` | Per-group MSE distributions (before/after) |
| `mitigation/device_fallback_impact.csv` | Before/after comparison metrics |
| `mitigation/single_feature_validation.json` | Single-feature sufficiency verdict |
| `forensic/per_feature_mse_decomposition.csv` | Per-feature MSE breakdown |
| `forensic/FORENSIC_REPORT.md` | Original forensic analysis |
| `retraining/evaluation_distributions.csv` | V5 baseline distributions |
