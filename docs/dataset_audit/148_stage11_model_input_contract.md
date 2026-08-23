# 148 — Model Input Contract (Tahap 11)

VAE menerima TEPAT 9 fitur, urutan tetap (identik kontrak Stage 9/10 dan
`CONFIG["input_dimension"]=9` model existing):

1. user_id · 2. activity · 3. status · 4. device · 5. ip_address ·
6. duration_ms · 7. object_count · 8. hour · 9. day_of_week

## Dilarang & terverifikasi tidak ada di matrix

- Label: anomaly_type, risk_level → hanya di companion CSV utk evaluasi.
- Integrity: hash, path, file, filename, target_tipe, target_id → tidak pernah
  menjadi fitur sejak Stage 8.

Validasi struktural: matrix dibangun dari `FEATURES` saja (Stage 10 check
`labels_not_in_matrix` PASS); input validation Tahap 11 memastikan shape (n,9).
