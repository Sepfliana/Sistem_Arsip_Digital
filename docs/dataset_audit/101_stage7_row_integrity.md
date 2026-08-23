# 101 — Integritas Row-Level Stage 7

Perbandingan penuh original vs Stage 6 (merge outer + indicator, dan `DataFrame.equals`):

| Metrik | Nilai | Expected | Status |
|---|---|---|---|
| rows_original | 15000 | 15000 | PASS |
| rows_stage6 | 15000 | 15000 | PASS |
| rows_missing | 0 | 0 | PASS |
| rows_added | 0 | 0 | PASS |
| rows_changed | 0 | 0 | PASS |
| frames_identical (equals) | TRUE | TRUE | PASS |

Tidak ada record hilang, tambahan, atau berubah isi. SHA-256 kedua file identik (`5e9bf0d5…9e966`) sehingga hasil struktural ini konsisten dengan checksum; pemeriksaan tetap dijalankan untuk dokumentasi sesuai instruksi Tahap 7.
