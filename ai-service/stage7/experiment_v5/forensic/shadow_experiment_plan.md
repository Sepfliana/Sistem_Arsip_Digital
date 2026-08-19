# Shadow Experiment Plan — V6 Domain-Aware Retraining

**Scope:** Experiment design only. NO training, NO code changes, NO production impact.
**Objective:** Test whether feature redesigns reduce localhost FPR without harming anomaly detectability.

---

## 1. Experiment Setup

### 1.1 Fixed Constraints
- **TRAIN_NORMAL dataset:** UNTOUCHED (same 8750 records as V5)
- **VALIDATION_NORMAL / TEST_NORMAL:** UNTOUCHED (same split)
- **VALIDATION_ANOMALY / TEST_ANOMALY:** UNTOUCHED (same synthetic anomalies)
- **VAE architecture:** UNTOUCHED (9→64→32→[mu=8,logvar=8]→8→32→64→9)
- **Training hyperparameters:** UNTOUCHED (seed=42, epochs=100, batch=64, lr=0.001, beta_kl=0.001)

### 1.2 Modified Components (V6 Candidate)
The following preprocessing functions are modified:

| Component | V5 | V6 Candidate |
|-----------|-----|-------------|
| `ip_address` | 6-category LabelEncoder | 2-category (Internal/External) |
| `duration_ms` | log1p(raw_ms) continuous | Binary (has_telemetry: 0/1) |
| `hour` | Raw hour (0–23) | 4-period categorical (Morning/Afternoon/Evening/Night) |
| `device` | Fallback: "Unknown Device" | Fallback: "PC Windows" |
| `activity` | 12 categories | 8 categories (merge rare → "Administrasi") |

### 1.3 New Data Requirement
V6 requires **reprocessed training data** with the redesigned features. The 8750 TRAIN_NORMAL records must be reprocessed through the new preprocessing pipeline to produce a V6 dataset.

**Critical:** The same raw data is used; only the canonical encoding changes.

---

## 2. Experiment Variants

### Variant A: Device-Only Fix (No Retraining)
- Apply only the `device` fallback fix ("Unknown Device" → "PC Windows")
- Use the existing V5 model (no retraining)
- **Purpose:** Test if a preprocessing-only fix reduces localhost FPR
- **Expected:** Moderate FPR reduction (device contributes 14.4% of MSE)

### Variant B: Full Feature Redesign (Retraining Required)
- Apply all 5 fixes (ip_address, duration_ms, hour, device, activity)
- Retrain VAE on V6 dataset
- **Purpose:** Test if redesigned features eliminate localhost domain shift
- **Expected:** Near-zero localhost FPR

### Variant C: Partial Fix — ip_address + duration_ms Only (Retraining Required)
- Apply only the 2 CRITICAL fixes
- Retrain VAE on V6 dataset (partial redesign)
- **Purpose:** Test if fixing the top2 features is sufficient
- **Expected:** Significant FPR reduction but residual gap from hour/device/activity

---

## 3. Evaluation Protocol

### 3.1 Evaluation Groups

| Group | Purpose | Records |
|-------|---------|---------|
| VALIDATION_NORMAL | Baseline — same as V5 | 1875 |
| TEST_NORMAL | Holdout — same as V5 | 1875 |
| VALIDATION_ANOMALY | Synthetic anomalies — same as V5 | 500 |
| TEST_ANOMALY | Holdout anomalies — same as V5 | 500 |
| **LOCALHOST** | **Domain shift target — same 329 records** | **329** |

### 3.2 Metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| **FPR_localhost_val** | localhost records classified as anomaly at validation threshold | ≤ 5% |
| **FPR_localhost_prod** | localhost records classified as anomaly at production threshold | ≤ 10% |
| **ROC_AUC_test** | Area under ROC curve on TEST_NORMAL + TEST_ANOMALY | ≥ 0.995 |
| **F1_test** | F1 score on TEST_NORMAL + TEST_ANOMALY | ≥ 0.990 |
| **Recall_test_anomaly** | Recall on TEST_ANOMALY only | ≥ 0.990 |
| **Precision_test_anomaly** | Precision on TEST_ANOMALY only | ≥ 0.990 |
| **MSE_gap** | LOCALHOST_min_MSE − TEST_NORMAL_max_MSE | Should be > 0 (gap preserved) |
| **KL_ratio** | KL(localhost) / KL(train_normal) | Should decrease toward 1.0 |

### 3.3 Threshold Selection
- **Validation threshold:** Selected at FPR=0.005 on VALIDATION_NORMAL (same as V5 methodology)
- **Production threshold:** Frozen from V5 (3.1496) for backward compatibility testing

### 3.4 Shadow Scoring
For each variant, score all 5 evaluation groups through the FULL inference pipeline:
1. Raw data → `process_record()` (with V6 preprocessing)
2. Canonical → LabelEncoder → StandardScaler
3. VAE forward pass → reconstruction error
4. Threshold classification

---

## 4. Acceptance Criteria

### Must Pass (ALL required to proceed to Stage 8)

| Criterion | Variant A | Variant B | Variant C |
|-----------|-----------|-----------|-----------|
| FPR_localhost_val ≤ 5% | — | ≤ 5% | ≤ 5% |
| ROC_AUC_test ≥ 0.995 | ≥ 0.995 | ≥ 0.995 | ≥ 0.995 |
| F1_test ≥ 0.990 | ≥ 0.990 | ≥ 0.990 | ≥ 0.990 |
| Recall_test_anomaly ≥ 0.990 | ≥ 0.990 | ≥ 0.990 | ≥ 0.990 |
| No regression in MSE_gap | ≥ 0 | ≥ 0 | ≥ 0 |

### Should Pass (Recommended, not blocking)

| Criterion | Target |
|-----------|--------|
| FPR_localhost_prod ≤ 10% | ≤ 10% |
| KL_ratio (localhost/train) < 2.0 | < 2.0 |
| Precision_test_anomaly ≥ 0.990 | ≥ 0.990 |

---

## 5. Failure Conditions

### Immediate Failure (Stop Experiment)
1. **ROC_AUC_test drops below 0.990** — model lost anomaly detection capability
2. **Recall_test_anomaly drops below 0.980** — missing real anomalies
3. **FPR_localhost_val increases** — fix made things worse
4. **Any leakage detected** — validation/test data contaminated with V6 preprocessing

### Warning Conditions (Investigate Before Proceeding)
1. FPR_localhost_val between 5%–15% — partial fix, may need additional variants
2. KL_ratio decreases but remains > 2.5 — residual domain gap
3. MSE_gap decreases but remains positive — gap narrowing but not closed

---

## 6. Comparison Framework

After all variants are evaluated, compare:

| Comparison | Question Answered |
|------------|------------------|
| V5 vs Variant A | Does device-only fix reduce FPR without retraining? |
| V5 vs Variant C | Do CRITICAL fixes alone solve the problem? |
| V5 vs Variant B | Does full redesign achieve near-zero FPR? |
| Variant C vs Variant B | Is the additional HIGH/MEDIUM fix worth the complexity? |

### Decision Matrix

| Outcome | Recommended Next Step |
|---------|----------------------|
| Variant A passes all criteria | Deploy device fix immediately; defer retraining |
| Variant C passes all criteria | Proceed to Stage 8 with V6 (partial redesign) |
| Variant B passes all criteria | Proceed to Stage 8 with V6 (full redesign) |
| No variant passes | Revisit feature design; consider excluding localhost from scoring |

---

## 7. Audit Trail

All experiment artifacts must be saved:

```
stage7/experiment_v5/forensic/shadow_v6/
├── variant_a/
│   ├── preprocessing_changes.json
│   ├── training_config.json
│   ├── evaluation_distributions.csv
│   ├── threshold_analysis.csv
│   └── experiment_metadata.json
├── variant_b/
│   └── (same structure)
├── variant_c/
│   └── (same structure)
└── comparison_summary.csv
```

---

## 8. What This Experiment Does NOT Test

- **Different VAE architectures** — architecture is frozen
- **Different training hyperparameters** — hyperparams are frozen
- **Different anomaly types** — only localhost FPR is tested
- **Production deployment** — this is offline evaluation only
- **Runtime performance** — inference speed is not measured
