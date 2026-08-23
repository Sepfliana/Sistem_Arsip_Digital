# 117 — Pipeline Feature Engineering (Tahap 8)

## Diagram proses

```
RAW AUDIT LOG (stage6, 15.000 x 13)
      |
      v
[1] Column classification
    A perilaku | B metadata/session | C label/ground truth
    D integrity subsystem | E identifier/reference | F terlarang utk VAE
      |
      v
[2] Behavioral feature identification
    user_id, activity, status, device, ip_address,
    duration_ms, object_count
      |
      v
[3] Timestamp-derived features (tanpa menggeser waktu)
    timestamp -> hour        (pandas dt.hour)
    timestamp -> day_of_week (pandas dt.dayofweek, Monday=0)
      |
      v
[4] Label separation
    anomaly_type, risk_level  -> ground truth saja
    is_anom/skor_anomali/tingkat_risiko TIDAK dibuat
      |
      v
[5] Integrity/hash/path separation
    hash chain/file/path/target_* -> bukan fitur VAE
    HASH INTEGRITY DETECTION != VAE BEHAVIORAL DETECTION
      |
      v
[6] Canonical 9-feature representation (pra-encoding)
    ai-service/dataset/feature_engineering/
    audit_log_dataset_stage8_features.csv
      |
      v
[STOP — Encoding & Scaling adalah Tahap 9]
```

## Prinsip yang dipegang

1. Stage 6 tidak ditimpa; artefak baru tersimpan terpisah (preservasi SHA-256 terverifikasi).
2. Derivasi hour/day_of_week murni baca timestamp — tidak ada penggeseran waktu.
3. Working hours 08:00–16:00, weekend, holiday = konteks analisis, BUKAN label anomali otomatis.
4. Kosakata activity/device tidak direname; canonical mapping tetap dokumentasi.
5. Encoding final (LabelEncoder/one-hot/IP mapping/log1p) dan scaling (StandardScaler) = Tahap 9.

## Sumber acuan yang dibaca

- docs/dataset_audit/ hasil Tahap 1–7 (baseline, temporal, integritas, matriks keputusan, validasi).
- `ai-service/preprocessing.py` (pipeline training legacy).
- `ai-service/utils/preprocessing_contract.py` + `ai-service/utils/preprocessing.py` (kontrak inferensi).
- `ai-service/dataset/generator/config.py` (vocab IP/device, rasio anomali).
- `ai-service/services/inference.py` (input shape (n,9), threshold deployment).
