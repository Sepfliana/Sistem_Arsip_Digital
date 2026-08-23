# Stage 7 — Validation Report

## 1. Tujuan
Memvalidasi bahwa `audit_log_dataset_stage6.csv` memenuhi seluruh aturan Tahap 5 dan tidak mengalami kerusakan pada Tahap 6 — tanpa perubahan apa pun.

## 2. Dataset yang Divalidasi
`ai-service/dataset/generator/raw/audit_log_dataset_stage6.csv` (15.000 × 13).

## 3. Baseline
Original dataset + angka terdokumentasi Tahap 1/3/4/6 (`96`, `97`, `t3_stats.json`, `t6_stats.json`, `14_dataset_baseline_report.md`).

## 4. File Integrity
8/8 PASS (`100`): SHA256_MATCH = TRUE; parse OK; encoding UTF-8-SIG valid; row/column/nama-kolom/urutan identik.

## 5. Row Integrity
rows_original = rows_stage6 = 15.000; missing = added = changed = **0**; frames identical (`101`).

## 6. Duplicate Validation
Exact duplicate **0** (tidak dihapus — memang tidak ada); same user+timestamp = 0; same session+activity = 0; multi-event sessions = 3.595 (desain workflow, bukan duplikat) (`102`).

## 7. Temporal Validation
Semua 7 metrik cocok baseline: total 15.000; jam kerja 11.633; <08:00 1.854; ≥16:00 1.513; weekday 10.802; weekend 4.198 (`103`). Δ=0.

## 8. Holiday Validation
27 tanggal SKB 2025 utuh, per-tanggal cocok baseline Tahap 3; total holiday records = **1.124**; 0 tanggal hilang; tetap karakteristik temporal, bukan anomali (`104`).

## 9. Activity Validation
10 kosakata asli dengan count persis sama (Login 3.595 … Kelola Kode Klasifikasi 98); tanpa rename; mapping kanonik tetap dokumentasi (`105`).

## 10. Operational Feature Validation
user_id 72 unik; device 9 jenis; IP internal 14.700 + publik; durasi 1–106.760 ms; object_count 1–200; Berhasil/Gagal = 14.550/450. **Tidak ada imputasi/fabrikasi** — atribut ini tetap synthetic, bukan rekonstruksi data real (`106`).

## 11. Label Leakage Validation
anomaly_type/risk_level tetap di raw sbg ground truth dan di luar fitur; is_anom/skor_anomali/tingkat_risiko tidak dibuat-buat. **Leakage = 0** (`107`).

## 12. VAE Feature Contract Validation
9 fitur cocok urutan kontrak; forbidden terms = 0 → **contamination = 0** (`108`).

## 13. Synthetic/Real Separation
Real added = **0**; artefak retraining lama tidak dipakai (`109`).

## 14. Hash/File/Path Separation
Tidak ada hash baru; chain DB tak disentuh; path/filename/hash bukan fitur → **integrity contamination = 0** (`110`).

## 15. Preprocessing Compatibility
Dry-run in-memory non-destruktif: shape (15000,9), float64, NaN=0, Inf=0, urutan fitur sesuai (`111`); preprocessing.py & artefak produksi tidak disentuh.

## 16. Distribution Consistency
9 dimensi distribusi (activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week, ip_category): max difference per nilai = **0**, semua PASS (`112`).

## 17. Quality Gate
**PASS = 14/14 · FAIL = 0 · WARNING = 0** (`113`).

## 18. Temuan
Tidak ditemukan masalah baru. Keterbatasan yang telah didokumentasikan sejak Tahap 1–5 tetap berlaku (atribut operasional real 'unknown' menunggu perbaikan upstream; kosakata v2 menunggu regenerasi; label in-sample generator) — semuanya DEFERRED, bukan cacat proses Tahap 6.

## 19. Kesimpulan
Seluruh quality gate PASS sehingga dataset hasil Tahap 6 adalah **VALID UNTUK DILANJUTKAN KE TAHAP PENGOLAHAN BERIKUTNYA** (feature engineering → encoding/scaling → dataset final VAE). Pernyataan kesiapan *training* belum dapat dibuat karena Tahap 8–11 belum dilaksanakan.
