# 122 — Audit Implementasi Preprocessing Existing (Tahap 9)

## A. Pipeline TRAINING — `ai-service/preprocessing.py`

| Aspek | Implementasi |
|---|---|
| Input | `dataset/generator/raw/audit_log_dataset.csv` |
| Urutan transformasi | parse timestamp → derive hour/day_of_week → drop 6 kolom → LabelEncoder → IP integer → StandardScaler |
| Encoder | `LabelEncoder` pada ENCODER_COLUMNS = activity, status, device (`preprocessing.py:35`) |
| IP | `ip_to_integer` = `int(ipaddress.ip_address(v))` — ordinal 32-bit penuh (`preprocessing.py:38-39,58`) |
| user_id | numerik int64 passthrough (tidak di-encode) |
| duration_ms / object_count | numerik mentah (tanpa log) |
| hour / day_of_week | passthrough hasil derivasi naive lokal |
| Scaler | `StandardScaler` fit pada seluruh data (`preprocessing.py:61-62`) |
| Feature order | FEATURE_COLUMNS 9 nama tetap (`preprocessing.py:24-34`) |
| Dimensi output | (n, 9) float64 |
| Persistensi | `dataset/preprocessed/X_train.npy`, `label_encoders.pkl` (hanya kunci activity/status/device), `scaler.pkl`, `preprocessing_metadata.json` |

## B. Pipeline INFERENCE — `utils/preprocessing_contract.py` + `utils/preprocessing.py`

| Aspek | Implementasi |
|---|---|
| Entry | `preprocess_for_inference(payload)` → `process_record()` |
| Activity | `map_canonical_activity` → 12 kelas kanonik (+UNKNOWN), grouping berbeda dari vocab training |
| Status | `map_canonical_status` → Berhasil/Gagal/UNKNOWN |
| Device | `parse_user_agent_device` → 7 DEVICE_CLASSES (regex UA) |
| IP | `map_ip_category` → 5 kategori string +UNKNOWN |
| user_id | float; fallback 1.0 bila invalid |
| duration/object_count | `np.log1p` (`transform_numeric_features`) |
| Timestamp | `parse_timestamp_wib`: naive dianggap UTC → konversi Asia/Jakarta |
| Encoder | memakai `label_encoders.pkl` produksi; `_encode_canonical_value` dengan fallback UNKNOWN/case-insensitive/0 |
| IP encoding | `ip_encoded = ... if "ip_address" in encoders else 0` → **karena pkl training tak punya kunci ip_address, nilai selalu 0** (`utils/preprocessing.py:75`) |
| Scaler | `scaler.pkl` produksi via `scaler.transform` |
| Dimensi output | (1, 9) float32 |

Persistensi inference = membaca artefak training; tidak ada encoder/scaler kedua yang dibuat saat runtime.
