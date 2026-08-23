# Stage 6 — Implementasi Perbaikan Dataset

## 1. Tujuan
Mengeksekusi HANYA aturan yang disetujui Tahap 5 (RULE A–P) terhadap dataset utama synthetic, tanpa keputusan metodologis baru.

## 2. Dataset Input
`ai-service/dataset/generator/raw/audit_log_dataset.csv` — 15.000 × 13, SHA-256 `5e9bf0d5…9e966`, commit `b9857fc1`.

## 3. Aturan Tahap 5 yang Diterapkan
A (no timestamp change), B–D (metadata kalender), E-interim (artefak pemetaan), K/L/M/O (protective checks), N (scan duplikat verification-only), P (pemisahan real). Rincian: `87_stage6_rule_execution_plan.md`.

## 4. Aturan yang Hanya Validasi
Seluruhnya — setiap proses menghasilkan laporan validasi tanpa menyentuh row-level (`98_stage6_thesis_process_table.md`).

## 5. Aturan yang Ditunda
- Penyelarasan kamus aktivitas & aktivitas baru → **DEFERRED_TO_GENERATOR_V2**.
- IP/device/duration/object_count pada data REAL → **DEFERRED_TO_APPLICATION_DATA_CAPTURE**.

## 6. Verifikasi Duplicate
Exact duplicate = **0**; multi-event per sesi = desain workflow (3.595 sesi) — sah. Tidak ada penghapusan (`72`, `73`).

## 7. Validasi Temporal
Distribusi per jam identik before/after (Δ=0 untuk seluruh 24 jam); timestamp changes = 0 (`88`).

## 8. Validasi Kalender
Weekday 10.802 · Weekend 4.198 · Holiday (SKB 2025, 27 tanggal) 1.124 · Non-holiday 13.876 · <08:00 1.854 · 08–15:59 11.633 · ≥16:00 1.513 — semua Δ=0 (`89`).

## 9. Validasi Activity
Kamus tetap 10 nilai; pemetaan kanonik tersimpan sebagai artefak dokumentasi saja (`90`). Rename/regenerasi = DEFERRED.

## 10. Validasi Operational Features
IP/device/duration/object_count: tidak ada imputasi/fabrikasi; perbaikan nyata ada di aplikasi (`91`).

## 11. Pemisahan Hash/File/Path
Tidak ditambahkan ke fitur; tidak ada hash dibuat/diubah; HASH INTEGRITY ≠ VAE ANOMALY dipertahankan (`92`).

## 12. Pemisahan Label
anomaly_type/risk_level tetap di raw sebagai ground truth; di luar fitur; skor_anomali/tingkat_risiko post-event dilarang masuk training (`93`).

## 13. Feature Contract
9 fitur tidak berubah; X_train.npy (15000×9); kontaminasi 0 (`94`).

## 14. Synthetic vs Real
Real 337 baris TIDAK digabung; file retraining lama tidak dipakai sebagai sumber (`95`).

## 15. Before vs After
13 metrik pada `96_stage6_before_after.csv`: semua difference = 0.

## 16. Dataset Output
`ai-service/dataset/generator/raw/audit_log_dataset_stage6.csv` — salinan identik utk reproducibility. Folder processed/ sengaja tidak dipakai karena tidak ada transformasi row-level disetujui.

**DATASET PRESERVED — NO ROW-LEVEL TRANSFORMATION APPROVED.**

## 17. Checksum
SHA-256 original == SHA-256 Stage 6 → **SHA256_MATCH = TRUE** (`97`).

## 18. Keterbatasan
(1) Masalah kosakata/aktivitas fiktif dan atribut real 'unknown' belum teratasi — memang bukan lingkup dataset existing (deferred upstream/generator v2). (2) Label evaluasi masih in-sample generator. (3) Kalender libur real 2026 belum diverifikasi. (4) Salinan Stage 6 identik — nilai tambahnya adalah jangkar checksum & titik mulai Tahap berikutnya, bukan perbaikan isi.

## 19. Reproducibility
Skrip `audit_g_stage6.py` (deterministik, read-only + satu salinan byte); metadata lengkap di `71`; lingkungan & commit di `69_dataset_rule_reproducibility.md`.
