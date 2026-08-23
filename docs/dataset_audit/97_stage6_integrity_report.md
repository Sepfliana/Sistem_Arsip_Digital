# 97 — Laporan Integritas Output Stage 6

| Item | Nilai |
|---|---|
| SHA-256 original (`audit_log_dataset.csv`) | `5e9bf0d5ce8b8552356291da59f35877ad745e78e748f82d42fa9f3255f9e966` |
| SHA-256 Stage 6 (`audit_log_dataset_stage6.csv`) | `5e9bf0d5ce8b8552356291da59f35877ad745e78e748f82d42fa9f3255f9e966` |
| **SHA256_MATCH** | **TRUE** |
| File size (keduanya) | 1.825.031 byte |
| Rows / Columns | 15.000 × 13 |
| Frame equality (pandas) | TRUE |

## Penjelasan

Tidak ada perubahan — salinan dibuat byte-per-byte (`shutil.copy2`), karena seluruh aturan Tahap 5 yang disetujui bersifat protektif/dokumentatif. Maka:

- Perubahan yang menyebabkan perbedaan: **tidak ada**
- Jumlah row berubah: 0 · kolom berubah: 0 · field berubah: 0

Lokasi: working copy berada di `ai-service/dataset/generator/raw/audit_log_dataset_stage6.csv`. Folder `dataset/processed/` sengaja TIDAK dipakai karena tidak ada row-level transformation yang disetujui (menghindari kesan dataset hasil transformasi); salinan identik inilah artefak resmi Stage 6 untuk reproducibility.
