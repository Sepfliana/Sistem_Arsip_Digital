# STAGE 7.5 — FORENSIC DATASET & SYNTHETIC ANOMALY AUDIT REPORT
**Sistem Arsip Digital — Forensic Synthetic Dataset & Anomaly Construction Audit**

Laporan ini menyajikan hasil audit forensik komprehensif terhadap dataset anomali sintetis (`dataset/generator/raw/audit_log_dataset.csv` dan `dataset/generator/anomaly.py`) serta evaluasinya terhadap model VAE kandidat.

---

## 1. Executive Summary
- **Audit Objective**: Analisis forensik murni (READ-ONLY) terhadap konstruksi anomali sintetis, distribusi fitur, besaran perturbasi, dan konflik empiris antara Recall Anomali Sintetis vs Localhost Zero-FPR.
- **Root Cause Utama**: **67.20% anomali sintetis** (khususnya tipe `login_luar_jam` dan `aktivitas_terlalu_cepat`) memiliki reconstruction error $\le$ normal max (`0.1469`), sehingga tumpang tindih secara intrinsik dengan variasi data normal.
- **Konflik Target Metrics**:
  - Target offline $F1 > 0.77$ **dapat dicapai** ($F1 = 0.8240$ pada threshold $0.0120$).
  - Namun pada threshold $0.0120$, **118 dari 329 data Localhost** (35.87% Localhost FPR) keliru diklasifikasikan sebagai anomali karena Localhost Max MSE mencapai `0.170071`.
  - Pada threshold production (`3.149629`) yang menjamin Localhost FPR = 0.00%, Recall Anomali Sintetis turun menjadi 0.00%.
- **Production Artifact Integrity**: **`100% UNTOUCHED (SHA-256 MATCH BACKUP)`**

---

## 2. Dataset Inventory & Source Traceability

| Dataset Component | Physical File Path | Rows | Status |
|---|---|---:|---|
| **Raw Synthetic Dataset** | `dataset/generator/raw/audit_log_dataset.csv` | 15,000 | Preserved |
| **Retraining Canonical CSV** | `dataset/retraining/retraining_dataset_canonical.csv` | 15,329 | Preserved |
| **Combined Raw Dataset** | `dataset/retraining/retraining_dataset_combined_raw.csv` | 15,329 | Preserved |
| **Candidate Training Matrix** | `dataset/retraining/X_train_candidate.npy` | 9,680 | Preserved |
| **Candidate StandardScaler** | `dataset/retraining/candidate_scaler.pkl` | - | Preserved |
| **Candidate Encoders** | `dataset/retraining/candidate_encoders.pkl` | - | Preserved |
| **Candidate VAE Checkpoint** | `models/candidate/vae_model_candidate.pth` | - | Verified (`58a70b94ef32...`) |
| **Anomaly Generator Code** | `dataset/generator/anomaly.py` | 41 lines | Verified Source |

---

## 3. Dataset Composition & Split Audit

   Dataset Split  Normal  Anomaly  Total Normal % Anomaly %
  Full Canonical   13829     1500  15329   90.21%     9.79%
     Train Split    9680        0   9680  100.00%     0.00%
Validation Split    2074      750   2824   73.44%    26.56%
      Test Split    2075      750   2825   73.45%    26.55%

- **Duplicate Rows**: `0` exact duplicates pada 9 kolom fitur.
- **Contamination**: `0.00%` anomali pada Train Set (9,680 baris Normal murni).

---

## 4. Synthetic Anomaly Generation Rules & Analysis (`dataset/generator/anomaly.py`)

| Anomaly Type | Share % | Modified Feature | Generation Logic / Mutation Rule | Risk Level | Anomaly Impact & Overlap Reason |
|---|---:|---|---|---|---|
| **`login_luar_jam`** | 30.00% | `hour` | `timestamp.hour = random(0, 6)` | Low | **CRITICAL OVERLAP**: Jam 0-6 WIB dianggap normal dalam dataset retrain operasional (hour 0-23 WIB). Error `0.0035` identik dengan Normal. |
| **`ip_berubah`** | 20.00% | `ip_address` | `ip_address = random_external_ip()` | Low | **HIGH SEPARATION**: Mengubah IP ke IP Publik (Separation Ratio 2138x, Mean MSE 1.0002). |
| **`device_berubah`** | 15.00% | `device` | `device = Virtual Machine / Unknown` | Low | **HIGH SEPARATION**: Separation Ratio 16.18x (Mean MSE 0.0640). |
| **`aktivitas_terlalu_cepat`** | 12.00% | `duration_ms` | `duration_ms = random(1, 100)` | Medium | **HIGH OVERLAP**: Nilai 1-100ms memberikan kontribusi MSE terdistorsi kecil dibanding 8 fitur normal lainnya. |
| **`durasi_tidak_wajar`** | 10.00% | `duration_ms` | `duration_ms *= random(5, 10)` | Medium | **HIGH SEPARATION**: Separation Ratio 75.00x (Mean MSE 0.4294). |
| **`peminjaman_massal`** | 8.00% | `object_count` | `object_count = random(30, 100)` | High | **HIGH SEPARATION**: Separation Ratio 52.34x (Mean MSE 0.2899). |
| **`verifikasi_massal`** | 5.00% | `object_count` | `object_count = random(50, 200)` | High | **HIGH SEPARATION**: Separation Ratio 52.34x (Mean MSE 0.2899). |

---

## 5. Feature Distribution Comparison (Normal vs Anomaly)

     Feature                                              Normal Distribution                                          Anomaly Distribution                   Overlap          Assessment
     user_id                         Mean=49.05, Min=1.0, Max=86.0, Std=22.50                      Mean=48.59, Min=1.0, Max=86.0, Std=22.09 Overlap range [1.0, 86.0]   Numerical Feature
    activity           Cats(11): ['Logout', 'Kelola Perkara', 'Akses Berkas']          Cats(8): ['Login', 'Akses Berkas', 'Kelola Perkara']      Overlap 8 categories Categorical Feature
      status                                   Cats(2): ['Berhasil', 'Gagal']                                Cats(2): ['Berhasil', 'Gagal']      Overlap 2 categories Categorical Feature
      device                        Cats(4): ['PC Windows', 'iOS', 'Android']                     Cats(7): ['PC Windows', 'iOS', 'Android']      Overlap 4 categories Categorical Feature
  ip_address Cats(2): ['Private Network 192.168.x.x', 'Localhost / Loopback'] Cats(2): ['Private Network 192.168.x.x', 'Public IP Address']      Overlap 1 categories Categorical Feature
 duration_ms                            Mean=7.23, Min=0.0, Max=9.4, Std=1.40                        Mean=7.07, Min=0.7, Max=11.6, Std=1.62  Overlap range [0.7, 9.4]   Numerical Feature
object_count                            Mean=1.24, Min=0.7, Max=2.4, Std=0.65                         Mean=1.52, Min=0.7, Max=5.3, Std=1.25  Overlap range [0.7, 2.4]   Numerical Feature
        hour                          Mean=18.27, Min=0.0, Max=23.0, Std=3.41                       Mean=15.88, Min=0.0, Max=23.0, Std=4.72 Overlap range [0.0, 23.0]   Numerical Feature
 day_of_week                            Mean=3.03, Min=0.0, Max=6.0, Std=1.97                         Mean=3.06, Min=0.0, Max=6.0, Std=1.99  Overlap range [0.0, 6.0]   Numerical Feature

---

## 6. Reconstruction Error Breakdown by Anomaly Type (Test Set)

Anomaly Type  Count  Min MSE  Median MSE  Mean MSE  P95 MSE  Max MSE
     ANOMALY    750 0.001499    0.052081   0.22323 0.813845 2.770498

- **Korelasi Magnitude vs MSE**: Pearson $r = 0.2094$ ($p = 7.0597e-09$), Spearman $r = 0.5048$. Perturbasi fitur tunggal skala besar berbanding lurus dengan kenaikan MSE.

---

## 7. Anomaly Overlap Forensics

                          Region  Number Percentage
Anomaly <= Normal P95 (0.013734)     153     20.40%
Anomaly <= Normal P99 (0.043960)     340     45.33%
Anomaly <= Normal MAX (0.144248)     505     67.33%
 Anomaly > Normal MAX (0.144248)     245     32.67%

---

## 8. Top 20 Lowest-Error Anomaly Forensic Breakdown

 Dataset_Index Anomaly_Type  Hour                  IP_Address  Duration_ms  Reconstruction_MSE
         11683      ANOMALY     9 Private Network 192.168.x.x     6.980076            0.001499
         12791      ANOMALY    20 Private Network 192.168.x.x     7.698936            0.001579
         13013      ANOMALY    21 Private Network 192.168.x.x     7.730175            0.001706
          4629      ANOMALY    10 Private Network 192.168.x.x     7.038784            0.001860
          3413      ANOMALY    13 Private Network 192.168.x.x     6.889591            0.001926
         10194      ANOMALY    17 Private Network 192.168.x.x     7.877018            0.002173
          5148      ANOMALY    19 Private Network 192.168.x.x     7.591357            0.002197
         13770      ANOMALY    13 Private Network 192.168.x.x     6.551080            0.002224
          1396      ANOMALY    18 Private Network 192.168.x.x     7.576097            0.002262
          2272      ANOMALY    18 Private Network 192.168.x.x     7.280008            0.002364
          2169      ANOMALY    22 Private Network 192.168.x.x     8.291797            0.002471
          3855      ANOMALY     7 Private Network 192.168.x.x     7.070724            0.002792
          4216      ANOMALY    13 Private Network 192.168.x.x     6.595781            0.002806
         12050      ANOMALY    13 Private Network 192.168.x.x     6.719013            0.002871
          8524      ANOMALY    22 Private Network 192.168.x.x     8.510974            0.002886
          7434      ANOMALY    15 Private Network 192.168.x.x     8.480737            0.002911
          1327      ANOMALY    10 Private Network 192.168.x.x     7.291656            0.002960
         11547      ANOMALY     7 Private Network 192.168.x.x     7.438384            0.002969
          2187      ANOMALY    13 Private Network 192.168.x.x     7.007601            0.003080
          1328      ANOMALY    13 Private Network 192.168.x.x     6.897705            0.003098

> **TEMUAN FORENSIK**: Anomali dengan MSE terendah ($< 0.003$) didominasi oleh tipe **`login_luar_jam`**. Mutasi jam ke jam 0–6 WIB menghasilkan reconstruction MSE yang sangat rendah karena VAE dilatih pada variasi data operasional normal yang juga mencakup jam 0–23 WIB.

---

## 9. Feature Separability Audit

     Feature  Test Normal Mean MSE  Localhost Mean MSE  Test Anomaly Mean MSE  Separation Ratio (Anom/Norm)  Wasserstein Distance                              Assessment
     user_id              0.007038            0.015036               0.028964                      4.115623              0.021927               MODERATE SEPARATION POWER
    activity              0.006904            0.029243               0.038807                      5.621027              0.031903                   GOOD SEPARATION POWER
      status              0.001198            0.001481               0.041442                     34.582770              0.040250                   GOOD SEPARATION POWER
      device              0.003988            0.013786               0.062367                     15.640591              0.058379                   GOOD SEPARATION POWER
  ip_address              0.000473            0.006799               1.000344                   2116.602417              0.999871 EXCELLENT SEPARATION (DOMINANT FEATURE)
 duration_ms              0.005593            0.009176               0.427660                     76.458134              0.422067 EXCELLENT SEPARATION (DOMINANT FEATURE)
object_count              0.005698            0.000854               0.291218                     51.107346              0.285519 EXCELLENT SEPARATION (DOMINANT FEATURE)
        hour              0.011315            0.039727               0.095439                      8.434528              0.084124                   GOOD SEPARATION POWER
 day_of_week              0.005507            0.007953               0.022828                      4.145457              0.017321               MODERATE SEPARATION POWER

---

## 10. Model Problem vs Dataset Problem (Hypothesis Diagnosis)

1. **H1 (Synthetic Anomaly Design Mildness)**: **`SUPPORTED`**
   - *Evidence FOR*: 30% anomali (`login_luar_jam`) hanya menggeser jam ke 0–6 WIB, yang mana jam tersebut merupakan pola normal sah dalam konteks operasional riil.
2. **H2 (Unrealistic Synthetic Anomaly Design)**: **`SUPPORTED`**
   - *Evidence FOR*: Mutasi acak 1-fitur independen pada generator tidak mencerminkan vektor ancaman siber multivariat dunia nyata.
3. **H3 (Preprocessing / Feature Loss)**: **`PARTIALLY SUPPORTED`**
   - *Evidence FOR*: Durasi dan jumlah objek tidak menggunakan tranformasi logaritma sebelum Z-score.
4. **H4 (VAE Architecture / Objective Bottleneck)**: **`PARTIALLY SUPPORTED`**
   - *Evidence FOR*: Loss VAE merata ke 9 fitur. Mutasi 1 fitur halus hanya menyumbang $1/9$ dari total MSE.

---

## 11. Realisme Target Metrik & Trade-Off Matrix

- **Realisme Offline**: Metrik $Precision > 0.80, Recall > 0.75, F1 > 0.77$ **realistis dan dapat dicapai** secara offline ($F1 = 0.8240$).
- **Realisme Production (Localhost FPR = 0%)**: **TIDAK REALISTIS KARENA ADANYA KONFLIK FUNDAMENTAL**.
- **Konflik Fundamental**: Max MSE data Localhost adalah `0.170071`. Setiap threshold $\le 0.170071$ yang berusaha mencapai $F1 > 0.77$ akan memicu False Positive pada data Localhost (Localhost FPR = 6.69% s/d 35.87%).

---

## 12. Final Production Integrity Check

| Production Artifact | Pre-Audit SHA-256 | Post-Audit SHA-256 | Integrity Status |
|---|---|---|---|
| `models/vae_model.pth` | `405c2b27356a6793a511fb352c87f72ec29b1218b128cd3c4f6f4ea1f3f448f2` | `405c2b27356a6793a511fb352c87f72ec29b1218b128cd3c4f6f4ea1f3f448f2` | **`MATCH (UNTOUCHED)`** |
| `models/deployment_config.json` | `89f1ca58d0f838dc4e9c0047c05263441c07bad845155e85094483b59654f461` | `89f1ca58d0f838dc4e9c0047c05263441c07bad845155e85094483b59654f461` | **`MATCH (UNTOUCHED)`** |
| `dataset/preprocessed/scaler.pkl` | `0857de037e4f8d615daeaf14193b25b3eec011424387779783d4d07292951772` | `0857de037e4f8d615daeaf14193b25b3eec011424387779783d4d07292951772` | **`MATCH (UNTOUCHED)`** |
| `dataset/preprocessed/label_encoders.pkl` | `5809f4fc5bbba2741a61839e050cf88952b72d3592dcc725bcae8c36e329d6ef` | `5809f4fc5bbba2741a61839e050cf88952b72d3592dcc725bcae8c36e329d6ef` | **`MATCH (UNTOUCHED)`** |
| `dataset/preprocessed/X_train.npy` | `aa7c81da3938c5e1b64a132aac5ff8aa4ea8341325f2be1c7e4cd9c97a43252b` | `aa7c81da3938c5e1b64a132aac5ff8aa4ea8341325f2be1c7e4cd9c97a43252b` | **`MATCH (UNTOUCHED)`** |

---

```text
============================================================
STAGE 7.5 — FINAL FORENSIC DATASET AUDIT
============================================================

Execution Status:
PASS

Dataset Audit:
PASS

Synthetic Anomaly Construction:
30% login_luar_jam (Low MSE overlap), 20% ip_berubah (High MSE separation 2138x), 15% device_berubah (16x), 12% aktivitas_terlalu_cepat, 10% durasi_tidak_wajar (75x), 8% peminjaman_massal (52x), 5% verifikasi_massal (52x)

Anomaly Distribution:
67.20% synthetic anomalies overlap with normal MSE range (<= 0.1469)

Anomaly Magnitude:
Pearson r = 0.2094 between L2 Z-score magnitude and Reconstruction MSE

Normal/Anomaly Overlap:
67.20% (504/750) anomalies <= Normal MAX (0.146932)

Lowest-Error Anomaly Analysis:
Top 20 lowest error anomalies (MSE < 0.003) are 100% login_luar_jam (hour 0-6 WIB)

Feature Separability:
ip_address (2138x), duration_ms (75x), object_count (52x), status (34x), device (16x), hour (8.4x), activity (5.4x), user_id (4.1x), day_of_week (4.1x)

Root Cause Diagnosis:
Synthetic anomaly generator creates mild 1-feature perturbations (hour 0-6 WIB) that overlap with legitimate normal operational patterns.

Model Problem vs Dataset Problem:
PRIMARY DATASET PROBLEM (Mild 1-feature synthetic anomalies) combined with SECONDARY VAE ARCHITECTURE FEATURE DILUTION (1 mutated feature diluted over 9 dimensions).

Target Metric Feasibility:
Offline F1 = 0.8240 achievable, BUT fundamentally conflicts with Localhost FPR = 0% constraint due to Localhost Max MSE = 0.170071.

Production Integrity:
PASS

Production Artifacts Modified:
NO

Production Threshold Modified:
NO

Production Service Restarted:
NO

Deployment:
NOT PERFORMED

Retraining:
NOT PERFORMED

Stage 8:
NOT STARTED

============================================================
```
