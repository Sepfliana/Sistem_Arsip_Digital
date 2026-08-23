# 139 — Cross-Split Leakage Check (Tahap 10)

## Pemeriksaan otomatis (137, PASS semua)

| Check | Hasil |
|---|---|
| Exact duplicate row lintas split (hash 9-fitur unscaled) | train-val = 0 · train-test = 0 · val-test = 0 |
| session_id menyeberang split | 0 sesi (group split by construction, diverifikasi ulang per baris) |
| Setiap baris tepat satu split | PASS (10.503 + 2.266 + 2.231 = 15.000) |
| Label di dalam matrix | tidak ada |

## Prinsip Tahap 6 tetap berlaku

Record TIDAK dihapus walau same user / same timestamp / same session / same
activity — itu desain workflow yang sah. Yang dicek hanyalah duplikasi identik
lintas split dan pemisahan grup sesi.

## Catatan leakage preprocessing

Stage 9 scaler fit pada seluruh data → diperbaiki metodologis di Tahap 10
dengan FINAL TRAINING SCALER fit hanya pada train (lihat 136/145 §9).
Scaler Stage 9 tidak di-overwrite; statusnya kini candidate/historis.
