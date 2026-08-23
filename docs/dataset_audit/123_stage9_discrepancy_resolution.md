# 123 — Resolution Discrepancy Tahap 8 (Tahap 9)

## D1 — Dokumentasi 10 fitur vs kode 9 fitur

- Source: `docs/VAE_ARCHITECTURE.md` vs `services/inference.py:26-27` (`shape[1] != 9`) dan `preprocessing.py:24-34`.
- Training: 9. Inference: memvalidasi (n,9). Kedua kode konsisten pada angka 9.
- Risiko: pembaca skripsi mengikuti dokumen usang.
- **Keputusan Tahap 9**: RESOLVED — kode adalah sumber kebenaran (9); `VAE_ARCHITECTURE.md` dicatat usang, tidak diedit di tahap ini.

## D2 — Training vs inference contract

| Komponen | Training | Inference | Risiko | Keputusan |
|---|---|---|---|---|
| IP | integer 32-bit | kategori string; encoder tak punya kunci ip → konstan 0 | distribusi fitur IP berbeda total saat serving | **BLOCKER utk parity deployment** — REQUIRED FOR LATER (Tahap 11/12): samakan representasi + retrain |
| duration/object_count | mentah | log1p | skala beda → reconstruction error bias | WARNING — DECISION diperlukan saat retraining |
| timestamp | naive lokal | naive dianggap UTC→WIB (geser −7 jam) | hour/day_of_week serving bergeser | WARNING — DECISION saat retraining/deployment |
| vocab activity/device | mentah sintetis | kanonik 12/7 kelas | label code tidak cocok antar-sisi | WARNING — terkait D3 |
| scaler | StandardScaler fit training | transform dengan scaler yang sama | ok asalkan input konsisten | PASS |

Tidak ada source code yang diubah pada Tahap 9.

## D3 — Tiga kosakata aktivitas

1. Sintetis 10 (dataset & training) — dipakai untuk dataset ini.
2. Kode aksi backend UPPER_SNAKE (produksi) — domain inference nyata.
3. Kanonik kontrak 12 kelas (`ACTIVITY_CLASSES`) — lapisan pemetaan inference.

**Keputusan**: encoding dataset Stage 8 memakai kosakata sintetis 10 apa adanya
(evidence: pipeline training existing yang menghasilkan model aktif). Pemetaan
kanonik tetap artefak dokumentasi. Compatibility problem dicatat di 129.
