# Reproducibility Notes — Audit Dataset Tahap 1 & 2

Tanggal eksekusi: 2026-08-23 · Mesin: Windows, PowerShell 5.1 · Git commit: `b9857fc16b2d7c54a4517da0173e45cce6d243af` (branch aktif, working tree hanya berisi penambahan folder docs/dataset_audit/)

## Prinsip

Seluruh proses READ-ONLY terhadap dataset, source code, model, threshold, dan konfigurasi. Tidak ada file di luar `docs/dataset_audit/` yang dibuat atau diubah. Query database hanya SELECT dan selalu diakhiri ROLLBACK.

## Environment

- Python: `ai-service/.venv/Scripts/python.exe` (venv project; Python 3.13.3)
- Dependency yang dipakai skrip audit: pandas, numpy (sudah ada di environment project); psycopg2 untuk query read-only
- Database: PostgreSQL `sistem_arsip_digital` @ localhost:5432

## Command yang dijalankan (berurutan)

```
ai-service\.venv\Scripts\python.exe docs\dataset_audit\audit_a_inventory_schema_quality.py
ai-service\.venv\Scripts\python.exe docs\dataset_audit\audit_b_distributions.py
ai-service\.venv\Scripts\python.exe docs\dataset_audit\audit_c_sop_validation.py
```

## Input

- `ai-service/dataset/generator/raw/audit_log_dataset.csv` (1.825.031 byte)
- `ai-service/dataset/retraining/retraining_dataset_combined_raw.csv`, `retraining_dataset_canonical.csv`
- `ai-service/dataset/dataset_vae.csv`, `dataset/processed/*.csv` (kosong), `dataset/preprocessed/X_train.npy`, `retraining/X_train_candidate.npy`, `preprocessing_metadata.json`
- Source code dibaca statis: `generator/*.py`, `preprocessing.py`, `train_vae_pytorch.py`, `services/inference.py`, `utils/preprocessing*.py`, `backend/services/auditLogService.js`, `backend/controllers/*.js`, `database/schema.sql`, `stage5_retraining_preparation_report.md`
- Tabel `audit_log` (+ JOIN users/roles) — SELECT-only

## Output (semua di docs/dataset_audit/)

Tahap 1: 01_dataset_inventory.csv · 02_dataset_origin_analysis.md · 03_actual_vae_data_flow.md · 04_schema_audit.csv · 05_quality_audit.csv · 06_timestamp_hour_analysis.csv (+06a_per_jam.csv, 06b_rentang.csv) · 07_calendar_analysis.csv · 08_activity_distribution.csv · 09_actor_distribution.csv · 10_network_distribution.csv · 11_file_integrity_audit.csv · 12_stage5_claim_verification.csv · 13_consistency_audit.md · 14_dataset_baseline_report.md · db_check.json · audit_summary.json

Tahap 2: 18_generator_behavior_analysis.md · 19_activity_sop_validation.csv · 20_role_activity_validation.csv · 21_working_hour_comparison.csv · 22_weekday_comparison.csv · 23_weekend_activity_analysis.md · 24_holiday_analysis.csv · 25_holiday_analysis.md · 26_operational_time_matrix.csv · 27_synthetic_real_comparison.csv · 28_synthetic_real_comparison.md · 29_dataset_gap_analysis.csv · 30_candidate_dataset_rules.md · 31_candidate_sop_dataset_table.md · 32_candidate_dataset_validation_narrative.md · db_tahap2.json

Skrip audit (dibuat khusus, tidak menyentuh source aplikasi): audit_a_inventory_schema_quality.py · audit_b_distributions.py · audit_c_sop_validation.py

Catatan: output 15–17 dari spesifikasi awal Tahap 1 tidak dibuat karena spesifikasi keluaran digantikan daftar Tahap 2 (tabel skripsi dilanjutkan sebagai 31 dan 32).

## Waktu eksekusi

Tiga skrip selesai dalam hitungan detik masing-masing (<10 s total); waktu persis tidak dicatat oleh skrip.

## Perubahan repository

Hanya: folder baru `docs/dataset_audit/` beserta isinya. `git status` pada saat audit menunjukkan tidak ada modifikasi lain (baseline commit b9857fc1). File dataset asli, generator, model, scaler, encoder, dan threshold tidak tersentuh — dapat diverifikasi ulang dengan membandingkan hash file dataset terhadap git (`git status --short ai-service/dataset` = bersih).
