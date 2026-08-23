# 46 — Proses Manajemen Audit Temporal Dataset

Proses yang dijalankan pada Tahap 3 (semua tahap bersifat AUDIT — tidak ada pembersihan, perbaikan, atau pembentukan dataset final):

1. **Ekstraksi timestamp.** Kolom `timestamp` diekstraksi dari dataset synthetic (`audit_log_dataset.csv`, 15.000 record) secara read-only; data real PostgreSQL (337 record) dibaca SELECT-only sebagai pembanding.
2. **Validasi format.** Seluruh 15.000 nilai tervalidasi pola `%Y-%m-%d %H:%M:%S`; tanpa nilai kosong/gagal-parse; tanpa zona waktu (naive) — dicatat sebagai keterbatasan.
3. **Pengelompokan berdasarkan jam.** Timestamp dikelompokkan ke 12 interval jam dan tiga kategori waktu (sebelum/jam kerja/setelah) → `33_hourly_distribution_detailed.csv`.
4. **Pengelompokan hari kerja/weekend.** Distribusi per hari mingguan (`35`) dan biner WORKDAY/WEEKEND (`36`).
5. **Verifikasi kalender.** Repository tidak memiliki sumber kalender → verifikasi eksternal terhadap SKB 3 Menteri 2025 via setkab.go.id (akses 2026-08-23) → `37_holiday_calendar_audit.csv`. Tidak ada daftar libur yang dikarang.
6. **Analisis kombinasi hari dan jam.** Klasifikasi analitis dua dimensi day_category × time_category dengan precedence HOLIDAY > WEEKEND > WORKDAY → `39_temporal_matrix.csv`.
7. **Perbandingan dengan data real.** Profil temporal synthetic vs real disusun paralel TANPA menggabungkan dataset → `41_temporal_synthetic_vs_real.csv`, narasi di `42`.
8. **Identifikasi gap.** Sembilan temuan temporal dikatalogkan dengan istilah *temporal characteristic / candidate issue / needs verification* → `43_temporal_issue_analysis.csv`; akar masalah ditelusuri ke logika generator → `40_generator_temporal_logic.md`.
9. **Penyusunan candidate rule.** Sembilan aturan kandidat direkomendasikan (status CANDIDATE / NEEDS_VERIFICATION / SUPPORTED_BY_DATA) → `44_candidate_temporal_rules.md`; angka baseline pra-perbaikan dikunci → `47_temporal_baseline.md`.

Setiap langkah meninggalkan artefak terukur sehingga proses dapat direproduksi (skrip `audit_d_temporal.py`, `audit_e_holiday.py`; catatan lingkungan di `reproducibility_notes.md`).
