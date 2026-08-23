# 69 — Reproducibility Perumusan Aturan (Tahap 5)

## Input
- Dataset: `ai-service/dataset/generator/raw/audit_log_dataset.csv` (15.000×13, tidak diubah).
- Real: tabel `audit_log` PostgreSQL 337 baris (SELECT-only, rollback; snapshot per sesi audit dicatat pada tiap file output).
- Source code dibaca statis: generator/*.py, preprocessing.py, services/inference.py, backend/services/auditLogService.js, backend/controllers/*, database/schema.sql.
- Kalender eksternal: SKB 3 Menteri No.1017/2024 & No.2/2024 via setkab.go.id (diakses 2026-08-23).

## Script audit yang menghasilkan evidence
- `audit_a_inventory_schema_quality.py`, `audit_b_distributions.py` (Tahap 1)
- `audit_c_sop_validation.py` (Tahap 2)
- `audit_d_temporal.py`, `audit_e_holiday.py` (Tahap 3)
- `audit_f_activity_file.py` + query berkas/verifikasi terdokumentasi (Tahap 4)

Semua output numerik pada 64_dataset_rule_decision_matrix.csv merujuk file CSV/MD bernomor di folder ini; tidak ada angka yang dikarang.

## Rule & decision
- Matriks keputusan: `64_dataset_rule_decision_matrix.csv` (40 baris, kolom Classification/Decision/Reason/Confidence).
- Aturan final RULE A–P: `65_dataset_cleaning_rules.md`.
- Spesifikasi before/after: `66_dataset_before_after_spec.md`.

## Alasan (ringkas per kategori)
- MUST_FIX → evidence lintas-tahap konsisten (kosakata aktivitas).
- DO_NOT_FIX / KEEP_AS_IS → melindungi metodologi (tanpa penghapusan weekend/libur/luar-jam; label keluar dari fitur).
- NEEDS_VERIFICATION → dokumen SOP/jam kerja, user_id leakage, duplikat persis, kalender 2026.

## Output yang diharapkan setelah Tahap 6
- Salinan dataset Stage 6 identik byte-per-byte dgn original (SHA256_MATCH = TRUE) karena seluruh aturan approved bersifat protektif/dokumentatif;
- artefak dokumentasi pemetaan aktivitas dan laporan validasi (71–99);
- nol perubahan pada generator, aplikasi, model, threshold, database.

## Lingkungan
Python venv proyek (`ai-service/.venv`), PowerShell; git commit dasar b9857fc16b2d7c54a4517da0173e45cce6d243af; semua perubahan repo terbatas pada folder docs/dataset_audit/.
