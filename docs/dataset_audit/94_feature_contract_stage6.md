# 94 — Kontrak Fitur VAE Stage 6

Kontrak fitur **TIDAK BERUBAH** dari pipeline aktif (`preprocessing.py`):

1. user_id
2. activity
3. status
4. device
5. ip_address
6. duration_ms
7. object_count
8. hour
9. day_of_week

## Verifikasi otomatis (audit_g_stage6.py)

- Parse `FEATURE_COLUMNS` dari source: cocok 9/9 dengan daftar di atas.
- Bentuk artefak aktif `X_train.npy` = **(15000, 9)** — konsisten, tidak tersentuh.
- Kontaminasi forbidden (hash/path/file/target_tipe/target_id/label anomali): **0 temuan**.

## Yang eksplisit BUKAN bagian fitur

hash_sebelumnya/hash_entri/file hash · path_file/nama_file · target_tipe/target_id · anomaly_type/risk_level/is_anom/skor_anomali/tingkat_risiko · session_id/username/timestamp mentah (hanya turunan hour/day_of_week yang menjadi fitur).

Status: **CONTRACT UNCHANGED — CLEAN**.
