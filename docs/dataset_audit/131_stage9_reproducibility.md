# 131 — Reproducibility Tahap 9

- **Input**: `ai-service/dataset/feature_engineering/audit_log_dataset_stage8_features.csv`
  SHA-256 `ce4854fae37d5c5ce4739784554aa9c20a9ff8dbe84f28541d924a47469ef959`
- **Input checksum verifikasi rantai**: Stage 6 tetap
  `5e9bf0d5…9e966` (dicek ulang script, PASS).
- **Script**: `docs/dataset_audit/audit_j_stage9.py` (v1.0), read-only terhadap sumber.
- **Encoder**: sklearn LabelEncoder ×3 (activity/status/device) — mapping tersimpan di
  `stage9_metadata.json` + `stage9_label_encoders.pkl` (`ai-service/dataset/encoded/`).
- **Scaler**: sklearn StandardScaler — mean/scale/var per fitur tersimpan di
  `stage9_metadata.json` + `stage9_scaler.pkl`.
- **Feature order**: user_id, activity, status, device, ip_address, duration_ms,
  object_count, hour, day_of_week.
- **Output**:
  - `audit_log_dataset_stage9_encoded.csv` (15.000×9 float64 ter-skalasi)
    SHA-256 `63801485f5e5c84dbe4453d214f811de62c75b8efd1e53bb917664303846affc`
  - `audit_log_dataset_stage9_encoded_unscaled.csv` (pre-scale, utk audit)
- **Execution timestamp**: 2026-08-23T15:05:01 (lokal; lihat t9_stats.json).
- **Git commit**: b9857fc16b2d7c54a4517da0173e45cce6d243af.

Ulangi dengan:
`ai-service\.venv\Scripts\python.exe docs\dataset_audit\audit_j_stage9.py`
→ seluruh 14 check + checksum output diregenerasi dan harus identik
(deterministik: LabelEncoder alphabetical + StandardScaler tanpa randomness).
