# 147 — Validasi Input Training (Tahap 11)

| Matrix | Shape | dtype | NaN | Inf | Checksum cocok Stage 10 |
|---|---|---|---|---|---|
| X_train_final.npy | (10503, 9) | float32 | 0 | 0 | fe67e6c8…a59f |
| X_validation_final.npy | (2266, 9) | float32 | 0 | 0 | f6e5185b…2af3 |
| X_test_final.npy | (2231, 9) | float32 | 0 | 0 | a2d02e16…3bc9 |

Semua sesuai metadata `final_dataset_metadata.json` (28/28 PASS Tahap 10).
Input validation dieksekusi di awal `audit_l_stage11.py` → `input_ok: True`.

Tidak ada dataset raw/Stage 6/Stage 8/candidate scaler/real PostgreSQL yang
dipakai sebagai input model.
