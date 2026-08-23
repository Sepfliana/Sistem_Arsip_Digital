# 116 — Reproducibility Tahap 7

- **Input**: `ai-service/dataset/generator/raw/audit_log_dataset_stage6.csv` (15.000×13).
- **Baseline**: `audit_log_dataset.csv` + angka terdokumentasi Tahap 1/3/4/6 (`96`, `97`, `98`, `99`, `t3_stats.json`, `t6_stats.json`).
- **Script**: `docs/dataset_audit/audit_h_stage7.py` — read-only terhadap dataset; satu-satunya penulisan = laporan CSV/JSON di folder ini.
- **Validation checks**: file integrity (8), row integrity (merge outer + equals), duplicate (4 kategori), temporal (7 metrik), holiday (27 tanggal + total), activity (10+vocab), operational features (6), preprocessing dry-run in-memory (shape/dtype/NaN/Inf/order), forbidden-term scan kontrak.
- **Output**: 100–106, t7_stats.json (+ dokumen MD 101–115).
- **Checksum**: original == stage6 = `5e9bf0d5ce8b8552356291da59f35877ad745e78e748f82d42fa9f3255f9e966` (di-hitung ulang pada Tahap 7, hasil sama).
- **Execution timestamp**: 2026-08-23 (sesi Tahap 7; lihat mtime `t7_stats.json` untuk detik).
- **Git commit**: `b9857fc16b2d7c54a4517da0173e45cce6d243af`.

Langkah ulang: jalankan script dengan interpreter venv proyek (`ai-service\.venv\Scripts\python.exe docs\dataset_audit\audit_h_stage7.py`) — seluruh PASS/FAIL diregenerasi otomatis.
