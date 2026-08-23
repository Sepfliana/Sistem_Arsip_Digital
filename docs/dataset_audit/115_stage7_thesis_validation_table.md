# 115 — Tabel Skripsi: Validasi Dataset Hasil Perbaikan (Tahap 7)

| No | Aspek Validasi | Kondisi Sebelum | Kondisi Sesudah | Hasil Validasi | Keterangan |
|---|---|---|---|---|---|
| 1 | Integritas berkas | Original 15.000×13, SHA-256 `5e9bf0d5…` | Stage 6 salinan byte-identik | PASS — SHA256_MATCH = TRUE | 100 |
| 2 | Integritas row-level | 15.000 record | missing=0; added=0; changed=0 | PASS — frames identical | 101 |
| 3 | Duplikat persis | 0 (hasil scan Tahap 6) | tetap 0 | PASS — tanpa penghapusan | 102 |
| 4 | Missing values | 0% pada kolom inti | tetap 0 | PASS — tanpa imputasi | 113 |
| 5 | Timestamp | Distribusi jam baseline Tahap 3 | identik (Δ=0, 24/24 jam) | PASS | 103 |
| 6 | Kalender (weekday/weekend/holiday) | 10802 / 4198 / 1124 (SKB 2025) | sama persis; 27 tanggal libur utuh | PASS | 103–104 |
| 7 | Kosakata aktivitas | 10 aktivitas asli + count baseline | sama; tanpa rename | PASS — mapping tetap dokumentasi saja | 105 |
| 8 | Fitur operasional (IP/device/duration/object_count) | Nilai sintetis bervariasi | tidak ada fabrikasi/imputasi baru | PASS — tetap synthetic, bukan rekonstruksi real | 106 |
| 9 | Label leakage | Label di luar fitur (kontrak preprocessing) | tetap di luar fitur | PASS — leakage = 0 | 107 |
| 10 | Kontrak fitur VAE | 9 fitur | cocok 9/9, kontaminasi 0 | PASS | 108 |
| 11 | Pemisahan real vs synthetic | Real 337 baris terpisah | real added = 0; artefak lama tak disentuh | PASS | 109 |
| 12 | Pemisahan hash/path/file | Integrity subsystem terisolasi | tetap terisolasi; chain tak disentuh | PASS — contamination = 0 | 110 |
| 13 | Kompatibilitas preprocessing | Kontrak aktif 9 fitur | dry-run in-memory: shape (15000,9), NaN=0, Inf=0 | PASS | 111 |
| 14 | Konsistensi distribusi | Baseline Tahap 1/3 | difference = 0 untuk seluruh dimensi yang dibandingkan | PASS | 112 |
| 15 | Checksum akhir | `5e9bf0d5…9e966` | sama | PASS | 113 gate #14 |

Interpretasi: seluruh quality gate PASS → dataset Stage 6 **VALID UNTUK DILANJUTKAN KE TAHAP PENGOLAHAN BERIKUTNYA** (feature engineering dst.), dengan catatan keterbatasan metodologis yang telah didokumentasikan pada Tahap 1–5.
