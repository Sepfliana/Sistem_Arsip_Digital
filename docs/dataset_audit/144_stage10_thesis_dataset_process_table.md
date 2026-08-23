# 144 — Tabel Skripsi: Proses Pembentukan Dataset VAE

| Tahap | Input | Proses | Output | Validasi |
|---|---|---|---|---|
| Dataset awal | Konfigurasi generator (seed 42, rasio 90/10) | Simulasi aktivitas 72 pengguna, 3.595 sesi, tahun 2025 + injeksi 7 jenis anomali (10%) | audit_log_dataset.csv 15.000×13 | Baseline Tahap 1; checksum tercatat |
| Perbaikan | Dataset awal | Keputusan RULES A–P (matriks 40 baris): preservasi penuh — tanpa cleaning/imputasi/rename; salinan byte-identik | audit_log_dataset_stage6.csv (SHA identik dgn asli) | Tahap 7: quality gate 14/14 PASS |
| Feature engineering | Stage 6 | Klasifikasi kolom A–F; derivasi timestamp→hour/day_of_week; pemisahan label & integritas | stage8_features.csv 15.000×9 pra-encoding | Kontrak fitur 10/10 PASS |
| Encoding | Stage 8 | LabelEncoder activity/status/device (alfabetis), IP→integer 32-bit, passthrough numerik | stage9_encoded(_unscaled).csv, encoder pkl + mapping metadata | Roundtrip exact; NaN/Inf=0; 14/14 PASS |
| Scaling | Hasil encoding | StandardScaler (kandidat, full-data) + dokumentasi parameter | stage9_scaler.pkl (candidate), CSV numerik | mean≈0/std≈1 |
| Splitting | Encoded unscaled | Group split by session_id, seed 42, 70/15/15 (2.516/539/540 sesi) | Indeks train/val/test; metadata companion per split | Grup disjoint; 0 overlap lintas split |
| Finalisasi | Train rows saja | FINAL TRAINING SCALER fit train-only → transform ketiga split → float32 | X_train/validation/test_final.npy + final_dataset_metadata.json | Shape/dtype/NaN/Inf/urutan/konstanta: 28/28 PASS |

Catatan metodologis utk skripsi: scaler final sengaja di-fit ulang hanya pada
train split untuk kontrol leakage — berbeda dari scaler kandidat Tahap 9 yang
fit full-data dan kini hanya bernilai historis.
