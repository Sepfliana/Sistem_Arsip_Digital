# 121 — Validasi Kontrak Fitur (Tahap 8)

Validator: `audit_i_stage8.py` → hasil mentah `121_stage8_contract_checks.csv`.

## Hasil

| Check | Expected | Status |
|---|---|---|
| stage6_sha_unchanged | `5e9bf0d5…9e966` sebelum & sesudah run | PASS |
| row_count | 15.000 | PASS |
| raw_column_count | 13 kolom persis kontrak Stage 6 | PASS |
| canonical_features_available | 9/9 tersedia/derivable | PASS |
| label_separation | anomaly_type/risk_level/is_anom/skor_anomali/tingkat_risiko tidak ada di fitur | PASS |
| hash_path_file_separation | 0 kebocoran hash/path/file/target_* | PASS |
| hour_derived_from_timestamp_no_shift | dt.hour murni, Δ=0 semua baris | PASS |
| day_of_week_convention | pandas Monday=0…Sunday=6, Δ=0 | PASS |
| no_missing_in_canonical | 0 NaN pada artefak kanonik | PASS |
| source_reread_sha_equal_after_run | SHA identik setelah eksekusi | PASS |

**FEATURE CONTRACT: PASS (10/10).** Input Stage 6 tidak berubah; artefak baru
hanya di `ai-service/dataset/feature_engineering/` dan `docs/dataset_audit/`.

## DISCREPANCIES (dicatat, TIDAK diperbaiki diam-diam)

- **D1**: `docs/VAE_ARCHITECTURE.md` menyebut 10 fitur; kode memaksa input (n, 9)
  (`services/inference.py:26`). Dokumentasi usang — yang berlaku adalah kode.
- **D2 — dua implementasi preprocessing**:
  - Training (`preprocessing.py`): LabelEncoder activity/status/device atas
    kosakata mentah; IP→integer penuh (`ip_to_integer`); duration/object_count
    mentah; timestamp naive lokal.
  - Inferensi (`utils/preprocessing_contract.py`): kosakata kanonik berbeda
    (12 activity classes, 7 device classes), IP→kategori string, duration &
    object_count→log1p, timestamp naive dianggap UTC lalu dikonversi WIB
    (potensi geser jam −7 utk data generator).
  - `label_encoders.pkl` hasil training hanya berisi kunci activity/status/device,
    sehingga jalur inferensi memakai `ip_encoded = 0` konstan
    (`utils/preprocessing.py:75`) sementara training melihat integer IP besar.
- **D3 — tiga kosakata aktivitas**: sintetis 10 (training), kode aksi backend
  UPPER_SNAKE (produksi), kanonik kontrak 12 (inferensi). Mapping Tahap 6 tetap
  artefak dokumentasi.

Semua discrepancy = WARNING metodologis untuk keputusan Tahap 9/retraining;
Tahap 8 tidak mengubah salah satu sisi.
