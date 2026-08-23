# 142 — Final VAE Contract (Tahap 10)

```
Input raw (generator, 15.000x13)
      |
      v
Stage 6  : audit_log_dataset_stage6.csv   (preserved; SHA 5e9bf0d5...9e966)
      |
      v
Stage 8  : feature engineering            -> dataset/feature_engineering/
            9 canonical features pra-encoding
      |
      v
Stage 9  : encoding + candidate scaling   -> dataset/encoded/
            LabelEncoder x3, IP integer, StandardScaler full-data (candidate)
      |
      v
Stage 10 : group split by session_id (seed 42; 70/15/15)
      |      final scaler = fit TRAIN ONLY (dataset/final/scaler/)
      v
X_train_final.npy      (10503, 9) float32
X_validation_final.npy ( 2266, 9) float32
X_test_final.npy       ( 2231, 9) float32
      |
      v
TAHAP 11 — VAE retraining & evaluasi (input resmi)
```

## Isi final matrix — HANYA fitur numerik perilaku

user_id, activity, status, device, ip_address, duration_ms, object_count,
hour, day_of_week (encoded + ter-skalasi final scaler).

## TIDAK berisi

- anomaly labels (anomaly_type) · risk labels (risk_level)
- hash / file path / filename / target_tipe / target_id
- timestamp mentah & session_id (hanya konteks companion metadata)

## Feature order

Tetap sesuai kontrak Stage 9 = kontrak model aktif `(n, 9)` — tidak ada
discrepancy urutan dengan source existing.
