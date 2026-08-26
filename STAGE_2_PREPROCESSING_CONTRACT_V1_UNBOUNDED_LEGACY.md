# STAGE 2 — Preprocessing Contract Finalization

## Preprocessing sebelum perubahan

Jalur training/inference historis tidak identik: inference legacy dapat memakai canonical fallback encoder, IP fallback/kategori alih-alih IPv4 integer 32-bit, `log1p` pada numeric yang training simpan raw, serta menganggap timestamp WIB naive sebagai UTC sehingga hour/day dapat bergeser. Artefak encoder dan scaler historis juga bukan pasangan eksplisit yang diturunkan dari train SSOT Tahap 1.

Endpoint legacy, model, arsitektur VAE, threshold, anomaly score, dan deployment **tidak diubah** pada Tahap 2.

## Preprocessing final

- Sumber data: `ai-service/dataset/final_stage1_ssot/` — train=6692, validation=4168, test=4140.
- Fungsi raw-to-feature tunggal: `utils.final_preprocessing_contract.records_to_unscaled_matrix()` dipakai oleh preparasi training dan adapter inference.
- Adapter masa depan `preprocess_for_inference()` memuat artifact ter-fit lalu menjalankan `transform` saja; tidak pernah `fit`.
- Tidak ada endpoint yang di-wire pada tahap ini.

## Feature order

`user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week`

## Encoder

- Satu artifact: `categorical_encoder.pkl` (`OrdinalEncoder`), fit hanya pada train normal.
- activity=10 kelas, status=2 kelas, device=5 kelas.
- Kategori yang tidak ada di train memakai encoder yang sama dengan kode unknown eksplisit `-1`; tidak ada encoder inference kedua atau refit pada validation/test.

## IP conversion

Training dan inference memakai `int(ipaddress.ip_address(value))` untuk IPv4 integer 32-bit unsigned. IPv6 ditolak; tidak ada representasi category/domain string.

## Numeric dan timezone

- `duration_ms` dan `object_count` adalah raw finite/non-negative value di kedua jalur; tidak ada `log1p`.
- Timestamp naive dianggap sudah WIB tanpa konversi UTC. Timestamp timezone-aware dikonversi ke `Asia/Jakarta`; `day_of_week` Monday=0.

## Scaler dan artifact

`train_only_scaler.pkl` di-fit sekali pada train normal (6692 baris; 0 anomali). Validation, test, dan inference hanya menjalankan `scaler.transform()`.

Artifact: `categorical_encoder.pkl`, `train_only_scaler.pkl`, `feature_contract.json`, matrix Stage 2 scaled/unscaled per split, `artifact_manifest.json`, dan `validation_results.json` dalam `dataset/final_stage1_ssot/preprocessing_stage2/`.

## Hasil parity dan special-case test

Parity train/inference menggunakan raw record yang sama dengan `atol=1e-07`, `rtol=0`.

- PASS — `artifact_exists_categorical_encoder.pkl`: ai-service/dataset/final_stage1_ssot/preprocessing_stage2/categorical_encoder.pkl
- PASS — `artifact_exists_train_only_scaler.pkl`: ai-service/dataset/final_stage1_ssot/preprocessing_stage2/train_only_scaler.pkl
- PASS — `artifact_exists_feature_contract.json`: ai-service/dataset/final_stage1_ssot/preprocessing_stage2/feature_contract.json
- PASS — `artifact_exists_artifact_manifest.json`: ai-service/dataset/final_stage1_ssot/preprocessing_stage2/artifact_manifest.json
- PASS — `feature_order_exact`: user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week
- PASS — `feature_count_9`: 9
- PASS — `encoder_columns_exact`: activity, status, device
- PASS — `encoder_is_single_training_fitted_encoder`: 3
- PASS — `scaler_fit_train_only`: {"type": "sklearn.preprocessing.StandardScaler", "fit_subset": "train only", "fit_rows": 6692, "fit_anomaly_rows": 0, "n_features": 9, "mean": [50.55304841601913, 5.298117154811716, 0.02973699940227137, 2.2023311416616855, 3232235898.133144, 2240.653466826061, 3.323819485953377, 11.588015540944411, 3.0026897788404066], "scale": [21.05232915931929, 3.056360800742384, 0.16986085561075512, 1.2571400165644893, 72.5918553347764, 1845.5006613875646, 3.0642473709998024, 2.8787813005172516, 1.9685950181498173], "var": [443.20056303232514, 9.341341344314628, 0.0288527102688178, 1.5804010212477644, 5269.577460945104, 3405872.691181938, 9.3896119506792, 8.287381776207798, 3.87536634548428]}
- PASS — `inference_trace_transform_only`: utils.final_preprocessing_contract.preprocess_for_inference
- PASS — `legacy_and_stage1_artifacts_preserved`: {"protected": {"count": 44, "unchanged": true}, "stage1": {"count": 13, "unchanged": true}}
- PASS — `train_has_zero_labelled_anomalies`: 0
- PASS — `train_training_matrix_reproducible`: unscaled=(6692, 9), scaled=(6692, 9)
- PASS — `train_matrix_shape_and_finiteness`: shape=(6692, 9), NaN=0, Inf=0
- PASS — `validation_training_matrix_reproducible`: unscaled=(4168, 9), scaled=(4168, 9)
- PASS — `validation_matrix_shape_and_finiteness`: shape=(4168, 9), NaN=0, Inf=0
- PASS — `test_training_matrix_reproducible`: unscaled=(4140, 9), scaled=(4140, 9)
- PASS — `test_matrix_shape_and_finiteness`: shape=(4140, 9), NaN=0, Inf=0
- PASS — `encoder_classes_derived_from_train_only`: {"activity": 10, "status": 2, "device": 5}
- PASS — `unknown_activity_same_fitted_encoder`: Tidak ada kategori evaluation di luar train.
- PASS — `unknown_status_same_fitted_encoder`: Tidak ada kategori evaluation di luar train.
- PASS — `unknown_device_same_fitted_encoder`: unseen=['Linux', 'MacOS', 'Unknown Device', 'Virtual Machine'], code=-1.0
- PASS — `training_inference_parity_same_raw_records`: records=9, max_abs_diff=0, atol=1e-07, rtol=0
- PASS — `special_all_categorical_values_training_inference_parity`: category_values_tested=21, atol=1e-07, rtol=0
- PASS — `special_ipv4_normal_32_bit_integer`: 192.168.1.8 -> 3232235784
- PASS — `special_loopback_converter_32_bit_integer`: 127.0.0.1 -> 2130706433
- PASS — `special_loopback_dataset_presence`: rows_in_ssot=0; converter tested directly because SSOT has no loopback row
- PASS — `special_timestamp_14_wib`: (14, 0)
- PASS — `special_timestamp_19_wib`: (19, 0)
- PASS — `special_timestamp_aware_to_wib`: (14, 0)
- PASS — `special_duration_and_object_count_raw`: duration_ms=1418.0, object_count=1.0
- PASS — `scaler_parameters_equal_train_only_statistics`: mean/variance from train unscaled only
- PASS — `scaler_train_output_normalized_float64`: float64 mean atol=1e-8, std atol=1e-12; stable for 32-bit IPv4 accumulation
- PASS — `scaler_train_output_float32_export_accuracy`: float32 mean atol=1e-6, std atol=5e-5
- PASS — `artifact_manifest_checksums_match`: artifacts=9

## File yang diubah

- `ai-service/utils/final_preprocessing_contract.py` (baru)
- `ai-service/finalize_preprocessing_stage2.py` (baru)
- `ai-service/validate_preprocessing_stage2.py` (baru)

## Status

**STAGE 2 — PASS**

Tidak ada retraining, perubahan model/arsitektur, threshold, anomaly score, atau deployment.
