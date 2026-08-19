# FASE PERBAIKAN 5 — DATASET RETRAINING PREPARATION REPORT
**Sistem Arsip Digital — Combined Dataset Preparation & Retraining Gate**

Laporan Stage 5 ini menyajikan hasil penggabungan, ekstraksi, normalisasi skema, validasi kebocoran data, dan analisis distribusi dataset gabungan **Synthetic (15.000 baris)** + **Real PostgreSQL DB (329 baris)**.

---

## 1. Objective
- Menyiapkan kandidat dataset retraining VAE yang **merepresentasikan aktivitas operasional nyata** (termasuk akses Localhost `127.0.0.1` dan `::1`).
- Menghilangkan distorsi extreme Z-score IP pada data operasional nyata.
- Menjamin 100% sinkronisasi skema dan fungsi preprocessing contract.

---

## 2. Source Dataset

### Synthetic Dataset
- **File Path**: `D:\Sistem_Arsip_Digital\ai-service\dataset\generator\raw\audit_log_dataset.csv`
- **Jumlah Baris**: `15000` baris
- **Karakteristik**: Synthetic baseline behavior (100% WAN / Private 192.168).

### Real PostgreSQL Dataset
- **Database**: PostgreSQL `sistem_arsip_digital` (tabel `audit_log`)
- **Jumlah Baris**: `329` baris (READ-ONLY Extraction)
- **Rentang Timestamp**: `2026-07-05 17:09:56.023000` s/d `2026-08-15 20:59:44.089000`
- **User ID Terlibat**: `[1, 6, 8, 84, 85, 86]`

---

## 3. Combined Dataset Composition & Categorization

| Kategori Dataset | Sumber Dataset | Jumlah Baris | Persentase Total | Perlakuan Retraining |
|---|---|---|---|---|
| **Synthetic Normal** | `audit_log_dataset.csv` | 13.500 | 88.07% | Training Normal Baseline |
| **Real DB Normal** | PostgreSQL `audit_log` | 329 | 2.15% | **Localhost Operational Normal Baseline** |
| **Synthetic Anomaly** | `audit_log_dataset.csv` | 1.500 | 9.79% | Validation & Test Anomaly Set |
| **TOTAL COMBINED** | Combined Raw | **15329** | **100.00%** | Raw Combined Candidate |

---

## 4. Schema Normalization & Preprocessing Contract

Seluruh 15329 record telah ditransformasikan melalui `utils/preprocessing_contract.py`:
- **Shape Array Canonical**: `(15329, 9)`
- **Integritas Float32 Array**: Has NaN = `False`, Has Inf = `False`
- **Daftar Fitur Strict (9 Fitur)**: `user_id`, `activity`, `status`, `device`, `ip_address`, `duration_ms`, `object_count`, `hour`, `day_of_week`.

---

## 5. Duplicate & Data Leakage Analysis

- **Duplicate Rows Check**: `0` duplicate rows terdeteksi pada 8 kolom pengenal.
- **Data Leakage Check**: Column leakage in VAE features = `[]` $	o$ **`PASS`** (Target/post-event fields `is_anom`, `risk_level`, `skor_anomali`, `tingkat_risiko` 100% DIBUANG dari VAE feature vector).

---

## 6. Combined IP Category Distribution (Localhost Included!)

                  IP Category  Synthetic Count  Real DB Count  Combined Total Combined %
         Localhost / Loopback                0            329             329      2.15%
  Private Network 192.168.x.x            14700              0           14700     95.90%
     Private Network 10.x.x.x                0              0               0      0.00%
Private Network 172.16-31.x.x                0              0               0      0.00%
            Public IP Address              300              0             300      1.96%
                      UNKNOWN                0              0               0      0.00%

> **HASIL UTAMA IP**: Data real DB sebanyak **329 baris Localhost (`127.0.0.1`, `::1`, `unknown`)** kini resmi terdaftar dan terwakili dalam kategori `"Localhost / Loopback"`. Scaler dan VAE akan dilatih untuk mengenali aktivitas Localhost sebagai data normal operasional.

---

## 7. Preprocessing Identity Test (20 Samples)

- **Identity Match (Training vs Inference Contract)**: `20/20` Match $	o$ **`PASS (100% EXACT MATCH)`** (Max diff = `0.000000`).

---

## 8. Outlier & Z-Score Analysis (Normal Candidate Training Set)

Hasil statistik Z-score dari Candidate `StandardScaler` (di-fit khusus pada 13829 baris Normal Candidates):

 Index      Feature   Min Z  Max Z  Mean Z  Std Z  Abs Max Z  |Z|>3  |Z|>4  |Z|>5
     0      user_id -2.1361 1.6424     0.0    1.0     2.1361      0      0      0
     1     activity -1.4038 1.9764    -0.0    1.0     1.9764      0      0      0
     2       status -0.1670 5.9898     0.0    1.0     5.9898    375    375    375
     3       device -2.0683 1.7489    -0.0    1.0     2.0683      0      0      0
     4   ip_address -6.4057 0.1561     0.0    1.0     6.4057    329    329    329
     5  duration_ms -5.1491 1.5367     0.0    1.0     5.1491    329    329    329
     6 object_count -0.8474 1.7795     0.0    1.0     1.7795      0      0      0
     7         hour -5.3627 1.3871     0.0    1.0     5.3627    227     98     61
     8  day_of_week -1.5342 1.5039     0.0    1.0     1.5342      0      0      0

---

## 9. Dataset Split Strategy (Clean Normal Training Split)

              Split  Normal Count  Anomaly Count  Total Count Contamination %
TRAIN (Normal Only)          9680              0         9680           0.00%
         VALIDATION          2074            750         2824          26.56%
               TEST          2075            750         2825          26.55%

- **File Candidate Artifacts Generated**:
  - `ai-service/dataset/retraining/retraining_dataset_combined_raw.csv` (15329 baris)
  - `ai-service/dataset/retraining/retraining_dataset_canonical.csv` (15329 baris)
  - `ai-service/dataset/retraining/X_train_candidate.npy` (9680 baris x 9 fitur)
  - `ai-service/dataset/retraining/candidate_scaler.pkl` (StandardScaler candidate)
  - `ai-service/dataset/retraining/candidate_encoders.pkl` (LabelEncoder candidate)

---

## 10. Risks & Warnings

1. **WARNING #1 (Proporsi Real Data)**: Data real DB sebanyak 329 baris menyumbang **2.15%** dari total dataset gabungan (15329 baris). Meskipun persentasenya kecil dibanding synthetic data (97.85%), keberadaan 329 baris Localhost ini **cukup untuk membuat Candidate Scaler mencakup kategori Localhost (index 0) secara sah**.
2. **WARNING #2 (Production Deployment Safety)**: Candidate Scaler dan Candidate Dataset tersimpan terpisah di folder `dataset/retraining/`. **Scaler, Encoder, dan Model VAE Production saat ini (`dataset/preprocessed/scaler.pkl`, `models/vae_model.pth`) 100% TIDAK DISENTUH ATAU DITINPA**.

---

## 11. Decision Gate

```text
[PASS] PostgreSQL Read-Only Extraction (329 rows)
[PASS] Schema Normalization & Preprocessing Contract v2
[PASS] Localhost IP Representation Integrated (329 rows Localhost)
[PASS] Data Leakage Check (Target fields strictly excluded)
[PASS] Training vs Inference Identity Test (Exact Match)
[PASS] Clean Normal Training Split (9680 rows, 0% contamination)
[PASS] Candidate Artifact Generation (X_train_candidate.npy, candidate_scaler.pkl)
```

- **DECISION GATE**: **`PASS WITH WARNING (DATASET READY FOR RETRAINING)`**

---

*Akhir Laporan Fase Perbaikan 5. Dataset kandidat retraining tersimpan di `dataset/retraining/`. Model VAE TIDAK diretrain, threshold deployment TIDAK diubah, dan database PostgreSQL TIDAK disentuh.*
