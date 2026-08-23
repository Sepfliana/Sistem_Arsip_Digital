# 119 — Before/After Feature Specification (Tahap 8)

## BEFORE — Raw audit log (Stage 6)

15.000 × 13: timestamp, session_id, user_id, username, role, activity, status,
ip_address, device, duration_ms, object_count, risk_level, anomaly_type.
Campuran fitur perilaku, metadata sesi, label ground truth, dan referensi
identitas dalam satu tabel.

## AFTER — Canonical feature representation (pra-encoding)

Artefak baru: `ai-service/dataset/feature_engineering/audit_log_dataset_stage8_features.csv`
(15.000 × 9):

| # | Fitur | Tipe semantik | Sumber |
|---|---|---|---|
| 1 | user_id | kategorikal identifier (72 unik) | raw |
| 2 | activity | kategorikal nominal (10) | raw |
| 3 | status | kategorikal biner | raw |
| 4 | device | kategorikal nominal (9 variasi) | raw |
| 5 | ip_address | konteks jaringan (362 unik) | raw |
| 6 | duration_ms | continuous behavioral | raw |
| 7 | object_count | count behavioral | raw |
| 8 | hour | numeric siklikal 0–17 teramati | timestamp.dt.hour |
| 9 | day_of_week | numeric ordinal kalender Senin=0 | timestamp.dt.dayofweek |

**CATATAN**: AFTER = representasi kanonik pra-encoding. BELUM encoded/scaled.
LabelEncoder, one-hot, IP category mapping, log1p, StandardScaler = Tahap 9.

## Yang dikeluarkan dari AFTER

- Label: risk_level, anomaly_type (ground truth evaluasi).
- Referensi/metadata: username, role, session_id, timestamp (sumber derivasi).
- Integrity subsystem: hash chain/file/path/target_* — memang tidak ada di raw,
  dan dipastikan tidak dibuat sebagai fitur.

## CANDIDATE FEATURES (tidak dimasukkan — butuh keputusan + regenerasi)

| Kandidat | Evidence | Manfaat | Risiko | Status |
|---|---|---|---|---|
| ip_category (5 kelas kontrak) | `utils/preprocessing_contract.py::map_ip_category` sudah ada; training memakai integer IP penuh | Representasi aman, hindari ordinalitas IP | Mengubah distribusi fitur → wajib retrain & re-threshold | DEFERRED (keputusan Tahap 9/retrain) |
| device_canonical (7 kelas) | Kontrak inferensi memetakan "Windows"/"Laptop Windows"→"PC Windows", "iPhone"→"iOS" | Sinkron train vs inference | Domain shift bila hanya satu sisi diubah | DEFERRED |
| is_weekend / is_holiday | Kalender SKB Tahap 3 | Fitur konteks eksplisit | Redundan dgn day_of_week+hour; menambah dimensi >9 kontrak model aktif | REJECTED utk kontrak 9; tersedia jika arsitektur diganti |
| activity_group (12 kelas kontrak) | map_canonical_activity | Menyatukan vocab produksi & sintetis | Menghapus granularitas kosakata sintetis tervalidasi | DEFERRED |
