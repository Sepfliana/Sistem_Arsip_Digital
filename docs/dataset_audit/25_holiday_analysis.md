# 25 — Analisis Tanggal Merah (Holiday)

Status keseluruhan: **NEEDS_VERIFICATION — TIDAK DAPAT DITENTUKAN**

## Hasil penelusuran

| Yang dicari | Hasil |
|---|---|
| File kalender/libur di repository (`*.csv/json/py/js` berisi daftar libur) | **tidak ditemukan** |
| Referensi "hari libur", "tanggal merah", "holiday" di kode/dokumentasi | **tidak ditemukan** (grep seluruh repo, kecuali file audit ini) |
| Logika kalender di generator synthetic | **tidak ada** — tanggal murni acak tahun 2025 |
| Logika kalender di preprocessing/VAE | **tidak ada** — hanya `hour` dan `day_of_week` yang diekstrak |

Sesuai aturan audit: karena project tidak memiliki sumber kalender yang dipakai/dirujuk, daftar tanggal merah 2025 maupun 2026 **tidak direkonstruksi dan tidak dikarang**. Kolom `holiday_status` pada `07_calendar_analysis.csv` (Tahap 1) dan baris `hari_libur` pada `26_operational_time_matrix.csv` diberi nilai **UNKNOWN**.

## Konsekuensi analisis

1. Kombinasi "hari libur × jam" pada 26_operational_time_matrix.csv tidak dapat dihitung per tanggal; seluruh baris dilaporkan sebagai UNKNOWN.
2. Dataset synthetic tidak dapat divalidasi terhadap tanggal merah karena tidak ada sumber acuan di project.
3. Data real (337 baris, rentang 2026-07-05 s/d 2026-08-19) juga belum dapat dianalisis terhadap tanggal merah dengan alasan yang sama.

## Yang dibutuhkan pada tahap berikutnya (rekomendasi, bukan pelaksanaan)

- Sumber kalender resmi yang disepakati (mis. daftar hari libur nasional & cuti bersama untuk tahun 2025 dan tahun berjalan) beserta dokumentasi asalnya, sehingga kolom holiday dapat diverifikasi dan direproduksi.
- Keputusan metodologis apakah tanggal merah akan menjadi fitur VAE, filter dataset, atau hanya konteks evaluasi — saat ini tidak ada satu pun yang diimplementasikan.
