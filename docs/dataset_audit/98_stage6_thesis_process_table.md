# 96/98 — Tabel Proses Skripsi Stage 6

| No | Proses Pengelolaan Dataset | Input | Perlakuan | Output | Hasil |
|---|---|---|---|---|---|
| 1 | Preservasi dataset asli | audit_log_dataset.csv | Hitung metadata+SHA-256; salin byte-identik | 71; stage6 copy | VALIDASI SAJA — TIDAK ADA PERUBAHAN DATA |
| 2 | Verifikasi duplicate | Working copy | Scan exact-dup & kategori konteks | 72, 73 | Exact duplicate = 0 — VALIDASI SAJA |
| 3 | Validasi timestamp | Kolom timestamp before/after | Banding distribusi per jam & kelompok | 88 | Δ=0 — VALIDASI SAJA |
| 4 | Validasi jam kerja | Bucket <08 / 08–15:59 / ≥16 | Metadata analisis (RULE B) | 89, 96 | VALIDASI SAJA — TIDAK ADA PERUBAHAN DATA |
| 5 | Validasi weekend | day_of_week | Count tetap 4.198 (RULE C) | 89 | VALIDASI SAJA |
| 6 | Validasi tanggal merah | Kalender SKB 2025 metadata | Count tetap 1.124 (RULE D) | 89 | VALIDASI SAJA |
| 7 | Validasi activity | 10 nilai aktivitas | Pemetaan kanonik DOCUMENT_ONLY, tanpa rename | 90 | ARTEFAK DOKUMENTASI — tanpa perubahan data |
| 8 | Validasi IP | ip_address | No imputation; upstream deferred | 91 | DEFERRED_TO_APPLICATION_DATA_CAPTURE |
| 9 | Validasi device | device | idem | 91 | DEFERRED_TO_APPLICATION_DATA_CAPTURE |
| 10 | Validasi duration | duration_ms | idem | 91 | DEFERRED_TO_APPLICATION_DATA_CAPTURE |
| 11 | Validasi object_count | object_count | idem | 91 | DEFERRED_TO_APPLICATION_DATA_CAPTURE |
| 12 | Pemisahan hash/path/file | Kontrak fitur | Cek forbidden terms = 0 | 92, 94 | SEPARATION INTACT — VALIDASI SAJA |
| 13 | Pemisahan label | anomaly_type, risk_level | Label dipertahankan di raw, di luar fitur | 93 | NO CONTAMINATION — VALIDASI SAJA |
| 14 | Validasi feature contract | preprocessing.py + X_train.npy | Parse FEATURE_COLUMNS; shape (15000,9) | 94 | CONTRACT UNCHANGED |
| 15 | Pemisahan synthetic dan real | Sumber training vs DB real | Real tidak masuk training; file retraining lama tidak disentuh | 95 | SEPARATION ENFORCED |
| 16 | Penyimpanan dataset Stage 6 | Salinan identik | Simpan raw/audit_log_dataset_stage6.csv | file Stage 6 | DATASET PRESERVED — NO ROW-LEVEL TRANSFORMATION APPROVED |
| 17 | Verifikasi checksum | Kedua file | SHA-256 compare | 97 | SHA256_MATCH = TRUE |
