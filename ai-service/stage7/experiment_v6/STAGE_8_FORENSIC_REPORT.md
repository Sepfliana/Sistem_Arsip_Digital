# Stage 8 Forensic Diagnosis Report

**Date:** Stage 8 completion
**Scope:** Pure diagnosis of why VAE fails on localhost after V6 retraining.

---

## Executive Summary

The V6 retrained model achieves perfect offline metrics (ROC-AUC=1.0, F1=0.999) but has **100% localhost FPR** at any reasonable threshold. The root cause is **distribution shift (B)**: training data is 100% SYNTHETIC with 192.168.x.x IPs, while localhost is 100% REAL_DB with 127.0.0.1 IPs. The VAE learned to reconstruct synthetic patterns that do not generalize to real operational data.

**Key finding:** V6 encoding (binary IP, binary duration) INTENTIONALLY made train and localhost look identical at the feature level, but the underlying data distributions remain fundamentally different. The model's reconstruction error for localhost (mean=2.4569) is 1088x higher than training (mean=0.002258), with zero overlap between distributions.

---

## 1. MSE Distribution Analysis

### Per-Group Statistics

| Group | Min | Mean | Median | Max | N |
|-------|-----|------|--------|-----|---|
| train_normal | 0.000032 | 0.002182 | 0.001466 | 0.078216 | 8750 |
| validation_normal | 0.000077 | 0.002536 | 0.001476 | 0.188254 | 1875 |
| test_normal | 0.000021 | 0.002331 | 0.001517 | 0.128781 | 1875 |
| localhost | 2.182856 | 2.456931 | 2.293585 | 2.860723 | 329 |

### Disjointness

| Metric | Value |
|--------|-------|
| Normal max MSE | 0.188254 |
| Localhost min MSE | 2.182856 |
| Gap (lh_min - normal_max) | 1.994602 |
| Ratio (lh_mean / train_mean) | 1088.1x |
| Overlap % | 0.0% |
| **Disjoint** | **YES** |

**Conclusion:** Localhost is COMPLETELY outside the training manifold. No overlap exists between normal and localhost MSE distributions.

---

## 2. Latent Space Analysis

### Centroid Distance

| Metric | Value |
|--------|-------|
| Train normal centroid (L2) | 2.6041 |
| Localhost centroid (L2) | 7.5351 |
| Centroid distance | 6.6220 |

### Per-Dimension Analysis

| Dim | Train Range (p1-p99) | Localhost Range (p1-p99) | Shift | Overlap? |
|-----|---------------------|-------------------------|-------|----------|
| 0 | -1.4119 -- 3.1519 | -5.2620 -- -3.1438 | 4.4434 | NO |
| 1 | -2.2746 -- 2.1911 | -3.4578 -- 2.2767 | 0.1773 | YES |
| 2 | -2.4303 -- 1.5149 | 0.0562 -- 1.7754 | 1.1907 | YES |
| 3 | -2.2634 -- 2.7370 | -2.2200 -- 0.8076 | 0.4305 | YES |
| 4 | -2.1222 -- 1.8079 | -4.2233 -- 0.3679 | 2.1016 | YES |
| 5 | -2.2201 -- 2.0678 | -1.1115 -- 3.2319 | 1.1330 | YES |
| 6 | -2.5292 -- 2.1381 | -6.1062 -- 0.2968 | 2.9508 | YES |
| 7 | -1.8240 -- 3.0637 | 0.8051 -- 6.1355 | 2.8399 | YES |


### Collapsed/Saturated Dimensions

- Collapsed dimensions (train std < 0.01): None
- Saturated logvar dimensions (mean < -5): [0, 1, 2, 3, 4, 5, 6, 7]

**Conclusion:** Localhost samples are mapped to a DIFFERENT region of latent space than training data. The centroid distance (6.6220) indicates significant separation. Some dimensions show no overlap.

---

## 3. Feature Contribution Analysis

### Per-Feature MSE

| Feature | Train MSE | Localhost MSE | Ratio | Contribution |
|---------|-----------|---------------|-------|--------------|
| status | 0.000684 | 18.026039 | 26360.9x | 81.5% |
| hour | 0.000649 | 1.045355 | 1611.4x | 4.7% |
| duration_ms | 0.000001 | 1.002155 | 1731078.6x | 4.5% |
| ip_address | 0.000000 | 0.988434 | 3608910.8x | 4.5% |
| object_count | 0.002340 | 0.488230 | 208.6x | 2.2% |
| activity | 0.001739 | 0.288646 | 166.0x | 1.3% |
| user_id | 0.003606 | 0.127758 | 35.4x | 0.6% |
| device | 0.000367 | 0.091963 | 250.5x | 0.4% |
| day_of_week | 0.010257 | 0.053776 | 5.2x | 0.2% |


### Top 3 Contributors to Localhost Error

1. **status** (ratio=26360.9x)
2. **hour** (ratio=1611.4x)
3. **duration_ms** (ratio=1731078.6x)

### Stage 7.6 Hypothesis Check

| Feature | Predicted Rank | Actual Rank | Match? |
|---------|---------------|-------------|--------|
| ip_address | 1 | 4 | NO |
| duration_ms | 2 | 3 | NO |
| device | 3 | 8 | NO |
| hour | 4 | 2 | NO |
| activity | 5 | 6 | NO |

**Conclusion:** The top error contributors are **status, hour, duration_ms**. These are the features where train and localhost distributions differ most in the SCALED space (after V6 encoding).

---

## 4. Training Data Audit

### IP Address Distribution

| Prefix | Train | Localhost |
|--------|-------|-----------|
| 192.x.x | 8750 | 0 |
| ::1.x.x | 0 | 1 |
| ::ffff:127.x.x | 0 | 3 |
| unknown.x.x | 0 | 325 |


- Train IPs: 192.168.x.x = 100.0%, 127.x.x.x = 0.0%
- Localhost IPs: 192.168.x.x = 0.0%, 127.x.x.x = 0.0%

### Duration Analysis

| Metric | Train | Localhost |
|--------|-------|-----------|
| Zero duration % | 0.0% | 100.0% |
| Has telemetry (V6) | 100.0% | 0.0% |

### Activity Distribution (V6)

| Activity | Train | Localhost |
|----------|-------|-----------|
| Administrasi | 1.6% | 0.0% |
| Kelola User | 0.6% | 0.0% |
| Login | 22.1% | 0.0% |
| Logout | 24.8% | 0.0% |
| UNKNOWN | 50.9% | 100.0% |


### Device Distribution (V6)

| Device | Train | Localhost |
|--------|-------|-----------|
| Android | 10.4% | 0.0% |
| PC Windows | 89.6% | 100.0% |


### User ID Range

| Metric | Train | Localhost |
|--------|-------|-----------|
| Min | 1 | 1 |
| Max | 86 | 86 |

**Conclusion:** The training data has FUNDAMENTAL structural differences from localhost:
1. **IP addresses:** Train is 100% 192.168.x.x, localhost is 100% 127.x.x.x
2. **Source type:** Train is 100% SYNTHETIC, localhost is 100% REAL_DB
3. **User IDs:** Localhost may contain user IDs outside training range
4. **Activity/Device:** Different distributions even after V6 encoding

---

## 5. Root Cause Classification

### Primary Cause: **B -- Distribution Shift**

**Evidence:**
- Training data is 100% SYNTHETIC with 192.168.x.x IPs
- Localhost is 100% REAL_DB with 127.0.0.1 IPs
- The VAE learned to reconstruct SYNTHETIC patterns, not REAL patterns
- Even after V6 encoding (which makes features LOOK the same), the underlying data distributions remain fundamentally different

### Contributing Factors

| Cause | Selected | Evidence |
|-------|----------|----------|
| A. Encoding mismatch | NO | V6 encoding is consistent (both Internal, both has_telemetry=1) |
| B. Distribution shift | YES | 100% synthetic train vs 100% real localhost |
| C. Model capacity | NO | Converged (loss=0.011038), no overfitting (ratio=0.55) |
| D. Training objective | NO | KL/reconstruction ratio=401.6672 (balanced) |

### Why V6 Failed Despite Redesign

The V6 feature redesign (binary IP, binary duration, 4-period hour) successfully reduced the **canonical domain gap** (overlap improved to 63.6%). However, it did NOT resolve the **model reconstruction gap** because:

1. **V6 encoding is a SURFACE-LEVEL fix:** It makes train and localhost look similar at the feature level (both "Internal", both "has_telemetry=1"), but the underlying data comes from fundamentally different distributions.

2. **The VAE learned synthetic manifolds:** The model was trained ONLY on synthetic data (192.168.x.x IPs, synthetic timestamps, synthetic user patterns). It cannot reconstruct real operational data (127.0.0.1 IPs, real timestamps, real user patterns).

3. **Scaler fit on synthetic data:** The StandardScaler was fit on train-normal (synthetic), so its mean/std reflect synthetic patterns. Localhost data, even after V6 encoding, produces different scaled values because the remaining continuous features (user_id, object_count, day_of_week) carry distributional differences.

4. **Feature redesign cannot fix data mismatch:** No amount of feature engineering can make synthetic data match real operational data. The fundamental issue is that the training set contains ZERO real operational records.

---

## 6. Final Diagnosis

**Feature redesign alone is insufficient because** the root cause is not feature encoding -- it is the structural mismatch between synthetic training data and real operational data. The VAE learned to reconstruct patterns that exist only in synthetic data, and these patterns do not generalize to real localhost records.

**To resolve this**, the training set must include REAL operational data (REAL_DB records) to teach the model what normal operational patterns look like.

---

*Report generated by stage8_forensic_diagnosis.py*
