# 93 — Pemeriksaan Pemisahan Label (RULE M)

## Status label pada dataset Stage 6

| Kolom label | Ada di raw CSV? | Masuk fitur VAE? | Peran sah |
|---|---|---|---|
| `anomaly_type` | YA (dipertahankan) | **TIDAK** — dibuang oleh preprocessing.py sebelum scaling | Ground truth evaluasi (definisi generator) |
| `risk_level` | YA (dipertahankan) | **TIDAK** — idem | Ground truth evaluasi |
| `is_anom` | TIDAK ADA di synthetic | — | n/a (istilah skema lain) |
| `skor_anomali` / `tingkat_risiko` | Hanya di tabel `laporan_anomali` (DB) | **TIDAK — post-event output model** | Hasil inference; dilarang jadi input (target leakage) |

## Verifikasi Stage 6

- FEATURE_COLUMNS hasil parse `preprocessing.py` = 9 fitur perilaku; tidak memuat satu pun nama label (`t6_stats.json.contract_features`).
- Label TIDAK dihapus dari raw dataset karena masih dibutuhkan sebagai ground truth/evaluasi — sesuai instruksi Tahap 6.
- Data real tidak digabung, sehingga `skor_anomali`/`tingkat_risiko` mustahil bocor masuk training set.

Status: **NO LABEL CONTAMINATION**.
