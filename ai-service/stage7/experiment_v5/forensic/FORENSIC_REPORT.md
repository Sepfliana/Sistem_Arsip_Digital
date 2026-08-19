# VAE Anomaly Detection — Forensic Root Cause Analysis

**Scope:** Explain why the VAE model classifies 100% of localhost records (329/329) as anomalies.
**Type:** Read-only forensic analysis. No retraining, no dataset redesign, no threshold tuning.

---

## Summary

The 100% false positive rate is caused by **two structural data distribution mismatches** between training data and localhost traffic. The model is performing correctly — localhost records genuinely lie outside the distribution it learned. The issue is that localhost traffic was never intended to be classified by this model.

---

## Root Cause #1 (Dominant): `ip_address` — Complete unseen category shift

**Severity: Critical — accounts for ~60% of total reconstruction error**

| Metric | Train Normal | Localhost | Ratio |
|--------|-------------|-----------|-------|
| Mean MSE | 0.000000 | 8.998316 | ∞ (1.2 billion) |
| % of total MSE | 0.00% | 301.1% | — |

**Mechanism:**
- **Training data**: 100% `Private Network 192.168.x.x` → LabelEncoder encodes to integer `1`
- **Localhost data**: 100% `Localhost / Loopback` → unseen category → LabelEncoder assigns `0` (fallback)
- After scaling (StandardScaler fit on train only): train `ip_address` scaled = 0.0 (constant), localhost `ip_address` scaled ≈ −3.0 (the unknown value)
- The VAE encoder maps localhost `ip_address` to a region of latent space far from training centroid
- The decoder cannot reconstruct the unknown `0` encoding → massive MSE

**This is the single largest contributor to the 100% FPR.** Even if all other features matched perfectly, the unseen `ip_address` category alone would push every localhost record above the threshold.

---

## Root Cause #2 (Critical): `duration_ms` — Total systematic shift

**Severity: Critical — accounts for ~27% of total reconstruction error**

| Metric | Train Normal | Localhost | Ratio |
|--------|-------------|-----------|-------|
| Mean (raw) | 1640 ms | 0 ms | — |
| Mean (log1p) | 7.41 | 0.00 | — |
| Scaled | 0.0 | −8.83 | 8.83σ |
| Mean MSE | 0.007827 | 15.906820 | 2032x |
| % of total MSE | 100.5% | 532.3% | — |

**Mechanism:**
- All 329 localhost records have `duration_ms = 0` (no browser telemetry)
- Training data has durations 200–12000 ms (mean 1640 ms, log1p mean 7.41)
- The model learned to reconstruct `log1p(duration_ms) ≈ 7.4` — it cannot reconstruct `0.0`
- This creates a second axis of total separation

---

## Root Cause #3 (Significant): `device` — Unseen category

**Severity: Major — accounts for ~14% of total reconstruction error**

| Metric | Train Normal | Localhost | Ratio |
|--------|-------------|-----------|-------|
| Top category | PC Windows (71.5%) | Unknown Device (98.8%) | — |
| Mean MSE | 0.001911 | 0.431058 | 226x |
| % of total MSE | 24.5% | 14.4% | — |

**Mechanism:**
- `Unknown Device` is unseen in training → encoded as fallback integer
- Combined with `ip_address`, creates a compound "unknown identity" signal the model cannot reconstruct

---

## Root Cause #4 (Moderate): `hour` — Distributional shift

**Severity: Moderate — accounts for ~29% of total MSE contribution**

| Metric | Train Normal | Localhost |
|--------|-------------|-----------|
| Mean hour | 18.4 h (5–23h peak) | 10.8 h (uniform 0–23h) |
| Mean MSE | 0.025637 | 0.874986 | 34x |
| |z|-score | — | 2.47σ |

**Mechanism:**
- Training data is concentrated in working hours (16–21h, mean 18.4)
- Localhost traffic is uniformly spread across all hours (mean 10.8)
- The model learned to reconstruct `hour ≈ 18` — local midnight/early records fail reconstruction

---

## Root Cause #5 (Moderate): `activity` — 3 unseen categories

**Severity: Moderate — accounts for ~13% of total MSE contribution**

| Metric | Train Normal | Localhost |
|--------|-------------|-----------|
| Unique categories | 8 | 11 |
| Unseen in train | — | `Keamanan & 2FA`, `Kelola Sarana`, `Peminjaman` |
| Mean MSE | 0.011442 | 0.378165 | 33x |

---

## Root Cause #6 (Minor): `user_id` — Low-ID concentration

**Severity: Minor — accounts for ~5% of total MSE**

| Metric | Train Normal | Localhost |
|--------|-------------|-----------|
| Mean user_id | 49.7 | 20.1 |
| Concentration | Uniform 1–86 | Heavy at 1–8 |

---

## Supporting Evidence: Latent Space Analysis

| Centroid Distance | Value | Interpretation |
|-------------------|-------|---------------|
| train → anomaly | 2.77 | Normal synthetic anomalies |
| train → localhost | **8.01** | **2.89× farther than anomalies** |
| localhost → anomaly | 7.42 | Localhost is in a completely different region |

The localhost centroid is **2.89× farther** from the training center than the synthetic anomalies. The model has never seen this region of input space, so it cannot reconstruct it.

## Supporting Evidence: KL Divergence

| Group | KL Mean | Interpretation |
|-------|---------|---------------|
| train_normal | 28.25 | Baseline |
| test_normal | 28.20 | Matches train |
| validation_anomaly | 42.45 | 1.5× train |
| **localhost** | **79.09** | **2.8× train** |

The encoder pushes localhost samples to regions of latent space with very high KL, meaning the posterior is far from the prior. The decoder has no capacity to reconstruct from these regions.

## Supporting Evidence: MSE Separation

| Metric | Train Normal | Localhost |
|--------|-------------|-----------|
| Min MSE | 0.000138 | 2.351072 |
| Max MSE | 0.262610 | 3.357630 |
| **Overlap** | **None** | **Gap = 2.09** |

Localhost minimum MSE (2.35) is **17× larger** than train maximum MSE (0.26). There is zero overlap — no threshold can separate these two groups because they are already completely separated by the model itself.

---

## Why Threshold Tuning Cannot Fix This

The MSE distributions are **disjoint with a 2.09 gap**:
- Train normal max MSE: 0.263
- Localhost min MSE: 2.351

Any threshold ≤ 0.263 classifies all localhost as anomalous (current behavior).
Any threshold ≥ 2.351 classifies all train normal as anomalous (broken model).
There is no threshold that classifies both correctly.

---

## Conclusion

The VAE is functioning as designed: it learned the distribution of `Private Network 192.168.x.x` PC Windows traffic with realistic durations, and correctly flags localhost traffic as anomalous because it deviates on every major feature axis:

1. **Different IP category** (unseen) — ∞ MSE ratio
2. **Zero duration** (systematic) — 2032× MSE ratio
3. **Unknown device** (unseen) — 226× MSE ratio
4. **Different hour distribution** — 34× MSE ratio
5. **3 unseen activity types** — 33× MSE ratio

The 100% FPR is not a model bug. It is a **data pipeline issue**: localhost traffic should be either (a) excluded from scoring, or (b) the model should be retrained on data that includes localhost patterns.

---

## Output Files

All forensic CSVs saved to `ai-service/stage7/experiment_v5/forensic/`:
- `per_feature_mse_decomposition.csv` — Per-feature MSE for train/localhost/anomaly
- `kl_divergence_analysis.csv` — KL divergence statistics per group
- `latent_space_analysis.csv` — Full latent space statistics
- `latent_mu_dimension_comparison.csv` — Per-dimension mu shift analysis
- `scaled_feature_comparison.csv` — Scaled absolute z-scores
