# 135 — Pemisahan Label pada Final Dataset (Tahap 10)

## Status label

`anomaly_type` (Normal + 7 jenis anomali) dan `risk_level` (Normal/Low/Medium/High)
TIDAK masuk ke X_train_final / X_validation_final / X_test_final.
Feature matrix dibangun murni dari 9 kolom kontrak (`labels_not_in_matrix` = PASS).

## Companion metadata (ground truth dipertahankan)

Ground truth TIDAK dibuang permanen. Disimpan pada file companion per split
(BUKAN input VAE):

- `train_metadata.csv`, `validation_metadata.csv`, `test_metadata.csv`
- Kolom: row_id, timestamp, user_id, activity, session_id, anomaly_type, risk_level.

## Peran label ke depan

- Evaluasi Tahap 11: menghitung deteksi anomali per jenis (recall per anomaly_type).
- Stratifikasi split: tidak digunakan sebagai fitur; hanya referensi distribusi
  (split memakai grouping session_id, lihat 136).
