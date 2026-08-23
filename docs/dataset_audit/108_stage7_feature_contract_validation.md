# 108 — Validasi Kontrak Fitur VAE Stage 7

Kontrak diharapkan (9 fitur, urutan tetap):

1. user_id · 2. activity · 3. status · 4. device · 5. ip_address · 6. duration_ms · 7. object_count · 8. hour · 9. day_of_week

## Hasil validasi

| Pemeriksaan | Hasil |
|---|---|
| FEATURE_COLUMNS hasil parse `preprocessing.py` | cocok 9/9, urutan sama |
| Kolom tersedia di Stage 6 + turunan hour/day_of_week dapat dibentuk | YA (dry-run in-memory sukses) |
| Forbidden terms (hash, previous_hash, current_hash, path, file, filename, target_tipe, target_id, anomaly_type, risk_level, is_anom, skor_anomali, tingkat_risiko) di kontrak | **0 temuan** |
| Bentuk matriks dry-run | (15000, 9), float64 |

**FEATURE CONTAMINATION = 0.**
