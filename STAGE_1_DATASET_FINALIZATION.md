# STAGE 1 — Dataset Finalization

## Dataset yang digunakan

- Basis forensic yang dipertahankan: `ai-service/dataset/generator/raw/audit_log_dataset_stage6.csv` (15.000 baris; SHA-256 `5e9bf0d5ce8b8552356291da59f35877ad745e78e748f82d42fa9f3255f9e966`).
- Representasi numerik sumber: `ai-service/dataset/encoded/audit_log_dataset_stage9_encoded_unscaled.csv` (9 fitur; SHA-256 `853c362859db26c9a3c1912addf6825bc3f8404da9d9939bff02fad747258055`).
- Mapping encoding tetap mereferensikan `dataset/encoded/stage9_label_encoders.pkl`; tidak ada perubahan pada preprocessing contract, model, threshold, skor anomali, atau deployment.

## Perubahan yang dilakukan

- Menambahkan `ai-service/finalize_dataset_stage1.py` sebagai finalisasi deterministik dari artefak Stage 6/9 yang sudah ada.
- Split sekarang berbasis `session_id`. Sesi normal dialokasikan 70%/15%/15% untuk train/validation/test (seed 42). Seluruh sesi yang berisi anomali berlabel dialokasikan utuh 50%/50% hanya ke validation/test.
- `dataset/final_stage1_ssot/` adalah single source of truth data untuk Tahap 2. Folder lama `dataset/final/` tidak diubah.

## Train / validation / test

| Subset | Rows | Sessions | Normal | Anomaly | Anomaly ratio |
|---|---|---|---|---|---|
| Train | 6692 | 1623 | 6692 | 0 | 0.00% |
| Validation | 4168 | 986 | 3416 | 752 | 18.04% |
| Test | 4140 | 986 | 3392 | 748 | 18.07% |

Train hanya berisi sesi yang seluruh barisnya berlabel `Normal`; anomali berlabel tidak dipakai untuk fit VAE maupun untuk fit scaler. Validation dan test mempertahankan baris normal serta anomali sebagai metadata/label evaluasi.

## Session leakage check

- Session overlap train/validation/test: `0 / 0 / 0`.
- Semua 15.000 baris memiliki tepat satu subset.
- Semua 1.500 anomali berlabel berada di validation atau test, bukan train.

## Feature check

- Matrix input berurutan tepat: `user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week`.
- Masing-masing matrix memiliki 9 kolom, `float32`, tanpa NaN atau Inf.
- `session_id`, `username`, `role`, `risk_level`, dan `anomaly_type` tidak berada pada matrix input; semua tetap tersedia di file metadata.

## Normal / anomaly composition

Per jenis anomali dan `risk_level` untuk setiap subset tersimpan di `final_dataset_metadata.json`; ringkasan row-level ditampilkan pada tabel di atas. Train: 0 anomali (0,00%).

## Artifact yang dihasilkan

- `X_train_final.npy` — SHA-256 `3d933c4ef4a77d79c7b60e3c00c9122886cd1d00968e055ace647b1395c6e2f9`
- `train_input_unscaled.csv` — SHA-256 `60148412f4280544538f6d7252d604a6ca3f1ea7977f06a487b405a8505eb8d6`
- `train_metadata.csv` — SHA-256 `f3f329f494f849d0ccf82c9283bd1c455526c85f0e756d2ec4b0dc521b604f4b`
- `X_validation_final.npy` — SHA-256 `10deb47805ff1f7be799e4bf0aa9c26c6492c92231ec2b5b5c7fabbd1b4d79a0`
- `validation_input_unscaled.csv` — SHA-256 `6de92a49d17564df099b9b7e6649aa95628a2018aedd82fbb4cc5724acf27448`
- `validation_metadata.csv` — SHA-256 `266d9d2328b2d3c432b3c30a124959b1938bbdf12e981097d30a59bd4f911d07`
- `X_test_final.npy` — SHA-256 `e8e4835c0a0f70c126f445d3369ef2a3c66ca7d369037167fd808a5bf7651adb`
- `test_input_unscaled.csv` — SHA-256 `3ed0a3e4eaa2b68020183143982943e7973726f95ebd1157da7469508c0aacd5`
- `test_metadata.csv` — SHA-256 `0dcc1cf2769a01a74591ae1f195206a939fbb6f746609c531f17036f7f8cbec7`
- `final_train_scaler.pkl` — SHA-256 `b97f0115a7658899fb5ce217c5daf162c71943611f43e069156a2bad8f767558`

Selain matrix, SSOT memuat `train/validation/test_input_unscaled.csv`, `train/validation/test_metadata.csv`, `final_train_scaler.pkl`, `final_dataset_metadata.json`, `validation_results.json`, dan `legacy_artifact_checksums.json`.

## File kode yang diubah

- `ai-service/finalize_dataset_stage1.py` (baru).

## Hasil validasi

- PASS — `source_exists_audit_log_dataset_stage6.csv`: ai-service/dataset/generator/raw/audit_log_dataset_stage6.csv
- PASS — `source_exists_audit_log_dataset_stage9_encoded_unscaled.csv`: ai-service/dataset/encoded/audit_log_dataset_stage9_encoded_unscaled.csv
- PASS — `source_exists_stage9_metadata.json`: ai-service/dataset/encoded/stage9_metadata.json
- PASS — `stage6_source_hash_matches_forensic_record`: 5e9bf0d5ce8b8552356291da59f35877ad745e78e748f82d42fa9f3255f9e966
- PASS — `source_row_alignment`: raw=15000, encoded=15000
- PASS — `source_row_count_15000`: 15000
- PASS — `source_feature_order`: user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week
- PASS — `source_feature_count_9`: 9
- PASS — `source_feature_numeric`: all numeric
- PASS — `source_no_nan_or_inf`: NaN=0, Inf=0
- PASS — `stage9_feature_contract_matches`: user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week
- PASS — `raw_required_metadata_present`: timestamp, session_id, user_id, username, role, activity, status, ip_address, device, duration_ms, object_count, risk_level, anomaly_type
- PASS — `raw_encoded_user_alignment`: row-for-row user_id
- PASS — `deterministic_session_assignment`: seed=42
- PASS — `session_sets_disjoint`: {"train_validation": 0, "train_test": 0, "validation_test": 0}
- PASS — `each_row_in_exactly_one_split`: assigned=15000/15000
- PASS — `train_contains_only_normal_labels`: 0
- PASS — `train_contains_only_normal_sessions`: train_sessions=1623
- PASS — `all_labelled_anomalies_reserved_for_evaluation`: evaluation=1500, total=1500
- PASS — `normal_session_ratio_70_15_15`: {"actual": {"train": 1623, "validation": 348, "test": 347}, "expected": {"train": 1623, "validation": 348, "test": 347}}
- PASS — `anomalous_sessions_only_validation_test_50_50`: {"actual": {"train": 0, "validation": 638, "test": 639}, "expected": {"train": 0, "validation": 638, "test": 639}}
- PASS — `forbidden_metadata_fields_not_input_features`: none
- PASS — `train_matrix_has_9_features`: (6692, 9)
- PASS — `train_matrix_float32`: float32
- PASS — `train_matrix_no_nan_or_inf`: NaN=0, Inf=0
- PASS — `train_input_csv_exactly_9_features`: user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week
- PASS — `validation_matrix_has_9_features`: (4168, 9)
- PASS — `validation_matrix_float32`: float32
- PASS — `validation_matrix_no_nan_or_inf`: NaN=0, Inf=0
- PASS — `validation_input_csv_exactly_9_features`: user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week
- PASS — `test_matrix_has_9_features`: (4140, 9)
- PASS — `test_matrix_float32`: float32
- PASS — `test_matrix_no_nan_or_inf`: NaN=0, Inf=0
- PASS — `test_input_csv_exactly_9_features`: user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week
- PASS — `scaler_fitted_on_train_normal_only`: fit_rows=6692
- PASS — `train_scaled_mean_zero`: StandardScaler train mean
- PASS — `train_scaled_nonconstant_features`: minimum std=0.9999999403953552
- PASS — `cross_split_exact_feature_row_overlap`: {"train_validation": 0, "train_test": 0, "validation_test": 0}
- PASS — `train_saved_matrix_matches_validated_input`: (6692, 9)
- PASS — `train_saved_input_csv_matches_contract`: rows=6692, columns=['user_id', 'activity', 'status', 'device', 'ip_address', 'duration_ms', 'object_count', 'hour', 'day_of_week']
- PASS — `train_saved_metadata_preserves_labels_and_session`: rows=6692
- PASS — `validation_saved_matrix_matches_validated_input`: (4168, 9)
- PASS — `validation_saved_input_csv_matches_contract`: rows=4168, columns=['user_id', 'activity', 'status', 'device', 'ip_address', 'duration_ms', 'object_count', 'hour', 'day_of_week']
- PASS — `validation_saved_metadata_preserves_labels_and_session`: rows=4168
- PASS — `test_saved_matrix_matches_validated_input`: (4140, 9)
- PASS — `test_saved_input_csv_matches_contract`: rows=4140, columns=['user_id', 'activity', 'status', 'device', 'ip_address', 'duration_ms', 'object_count', 'hour', 'day_of_week']
- PASS — `test_saved_metadata_preserves_labels_and_session`: rows=4140
- PASS — `legacy_and_production_artifacts_unchanged`: checked_files=46

Artefak lama tervalidasi aman: 46 file sumber/production/legacy memiliki checksum yang sama sebelum dan sesudah finalisasi.

## Status

**STAGE 1 — PASS**

Tahap 2 tidak dijalankan. Tidak ada retraining yang dilakukan.
