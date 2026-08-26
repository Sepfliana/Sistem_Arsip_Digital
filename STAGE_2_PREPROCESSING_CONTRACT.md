# STAGE 2 — Preprocessing Contract Finalization

## Status kontrak

**STAGE 2 — PASS**

Kontrak v1 sebelumnya membuktikan parity tetapi audit integrasi menemukan z-score IP tidak terbatas: train normal hanya berisi rentang `192.168.1.*` sehingga IPv4 valid di luar rentang itu menghasilkan input multi-juta-sigma dan mendominasi reconstruction error. V1 dipreservasi di `ai-service/dataset/final_stage1_ssot/preprocessing_stage2_v1_unbounded_legacy/`; tidak ada artifact yang dihapus.

## Kontrak final v2

- Sumber: SSOT Tahap 1 (`6.692` train normal, `4.168` validation, `4.140` test), session split tidak diubah.
- Urutan 9 fitur: `user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week`.
- `activity`, `status`, dan `device`: satu `OrdinalEncoder`, fit hanya train normal, inference `transform` artifact yang sama.
- IP: IPv4 tetap `int(ipaddress.ip_address(value))` unsigned 32-bit; IPv6 ditolak. Setelah `StandardScaler.transform()` train-only, hanya z-score IP dibatasi deterministik `(-3.0, 3.0)`. Ini bukan kategorisasi IP, bukan weighting, dan tidak memakai label/threshold; ia mencegah distorsi nilai tak-terbatas sambil mempertahankan satu feature IP.
- `duration_ms` dan `object_count`: raw non-negatif, tanpa `log1p`.
- Timestamp naive adalah WIB; timestamp aware dikonversi ke Asia/Jakarta; `day_of_week` Monday=0.
- Scaler hanya fit train normal. Validation/test/inference hanya transform yang sama, lalu bound IP kontraktual yang sama.

## Artifact final

`categorical_encoder.pkl`, `train_only_scaler.pkl`, `feature_contract.json`, matrix unscaled/final untuk tiga split, `artifact_manifest.json`, dan `validation_results.json` di `ai-service/dataset/final_stage1_ssot/preprocessing_stage2/`.

## Parity dan special case

Toleransi eksplisit: `atol=1e-07`, `rtol=0`.

- PASS — `artifact_exists_categorical_encoder.pkl`: D:\Download\Sistem_Arsip_Digital\Sistem_Arsip_Digital\ai-service\dataset\final_stage1_ssot\preprocessing_stage2\categorical_encoder.pkl
- PASS — `artifact_exists_train_only_scaler.pkl`: D:\Download\Sistem_Arsip_Digital\Sistem_Arsip_Digital\ai-service\dataset\final_stage1_ssot\preprocessing_stage2\train_only_scaler.pkl
- PASS — `artifact_exists_feature_contract.json`: D:\Download\Sistem_Arsip_Digital\Sistem_Arsip_Digital\ai-service\dataset\final_stage1_ssot\preprocessing_stage2\feature_contract.json
- PASS — `artifact_exists_artifact_manifest.json`: D:\Download\Sistem_Arsip_Digital\Sistem_Arsip_Digital\ai-service\dataset\final_stage1_ssot\preprocessing_stage2\artifact_manifest.json
- PASS — `contract_version_final_bounded_ip`: stage2-final-v2-bounded-ip-zscore
- PASS — `feature_order_exact_9`: user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week
- PASS — `non_input_fields_not_in_matrix`: metadata/labels excluded
- PASS — `encoder_train_only_three_categoricals`: ['activity', 'status', 'device']
- PASS — `scaler_train_normal_only`: 6692 train / 0 anomaly
- PASS — `v1_unbounded_artifact_preserved`: D:\Download\Sistem_Arsip_Digital\Sistem_Arsip_Digital\ai-service\dataset\final_stage1_ssot\preprocessing_stage2_v1_unbounded_legacy
- PASS — `train_reproducible`: shape=(6692, 9)
- PASS — `train_finite_shape`: shape=(6692, 9)
- PASS — `train_ip_zscore_bounded`: min=-1.572258, max=1.816552
- PASS — `validation_reproducible`: shape=(4168, 9)
- PASS — `validation_finite_shape`: shape=(4168, 9)
- PASS — `validation_ip_zscore_bounded`: min=-3.000000, max=1.816552
- PASS — `test_reproducible`: shape=(4140, 9)
- PASS — `test_finite_shape`: shape=(4140, 9)
- PASS — `test_ip_zscore_bounded`: min=-3.000000, max=1.816552
- PASS — `scaler_parameters_from_train_raw_only`: mean/variance exact from train raw matrix
- PASS — `training_inference_parity_same_raw`: max_abs_diff=0; atol=1e-07; rtol=0
- PASS — `special_all_categorical_values_parity`: activity/status/device train and unseen evaluation values
- PASS — `special_ipv4_integer_and_bounded_parity`: normal_private=192.168.1.8->3232235784,z=-1.572; loopback=127.0.0.1->2130706433,z=-3.000; other_private=10.0.0.1->167772161,z=-3.000; public=8.8.8.8->134744072,z=-3.000
- PASS — `special_timestamp_14_wib`: (14, 0)
- PASS — `special_timestamp_19_wib`: (19, 0)
- PASS — `special_timestamp_midnight_day`: Sunday 23:59 -> Monday 00:00
- PASS — `special_numeric_raw`: duration_ms/object_count unchanged before scaling
- PASS — `manifest_output_checksums`: count=9

## File kode

- `ai-service/utils/final_preprocessing_contract.py`
- `ai-service/finalize_preprocessing_stage2.py`
- `ai-service/validate_preprocessing_stage2.py`

