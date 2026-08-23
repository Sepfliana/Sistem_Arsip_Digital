# 71 — Integritasi Dataset Original (pra-Tahap 6)

Snapshot sebelum tindakan apa pun (metode: `audit_g_stage6.py`, hashlib SHA-256):

| Atribut | Nilai |
|---|---|
| Path | `ai-service/dataset/generator/raw/audit_log_dataset.csv` |
| File size | 1.825.031 byte |
| Row count | 15.000 |
| Column count | 13 |
| **SHA-256** | `5e9bf0d5ce8b8552356291da59f35877ad745e78e748f82d42fa9f3255f9e966` |
| mtime file | 2026-07-27T14:50:12 |
| Git commit | `b9857fc16b2d7c54a4517da0173e45cce6d243af` |
| Waktu snapshot | 2026-08-23T13:55:48 |

Working copy Stage 6 dibuat di `ai-service/dataset/generator/raw/audit_log_dataset_stage6.csv` via salinan byte (`shutil.copy2`) — checksum identik (lihat `97_stage6_integrity_report.md`). Original tidak ditimpa, tidak diedit.

Verifikasi frame: `df_original.equals(df_stage6)` = TRUE (pandas, 15.000×13).
