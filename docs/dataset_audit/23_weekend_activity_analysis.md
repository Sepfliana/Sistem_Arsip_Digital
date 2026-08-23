# 23 — Analisis Aktivitas Weekend

Prinsip: weekend TIDAK diperlakukan sebagai anomali. Hanya distribusi faktual.

## Synthetic (15.000 baris, tahun 2025)

| Kategori | Jumlah | Persentase |
|---|---|---|
| Weekday (Sen–Jum) | 10.802 | 72,01% |
| Weekend (Sab–Min) | 4.198 | 27,99% |

Per hari (22_weekday_comparison.csv): Senin 13,49% · Selasa 13,78% · Rabu 14,49% · Kamis 14,68% · Jumat 15,57% · Sabtu 13,65% · Minggu 14,33%.

Interpretasi faktual: sebaran per hari hampir seragam — konsisten dengan generator yang memilih tanggal acak tanpa membedakan weekend (lihat 18_generator_behavior_analysis.md butir 13). Tidak ada pola "weekend lebih sedikit" seperti sistem operasional nyata pada umumnya.

## Real PostgreSQL (337 baris)

| Kategori | Jumlah | Persentase |
|---|---|---|
| Weekday (Sen–Jum) | 232 | 68,84% |
| Weekend (Sab–Min) | 105 | 31,16% |

Per hari: Senin 1,19% · Selasa 28,19% · Rabu 21,07% · Kamis 18,40% · **Jumat 0%** · Sabtu 9,79% · Minggu 21,37%.

Catatan faktual (bukan label anomali):
- Porsi weekend real (31%) justru sedikit LEBIH TINGGI daripada synthetic acak (28%) — mengindikasikan aktivitas di log real banyak berasal dari proses non-kerja (pengujian/skrip; didukung temuan device='unknown' dan User-Agent axios).
- Jumat = 0 event dan Senin sangat rendah adalah karakteristik sampel kecil periode 2026-07-05 s/d 2026-08-19, bukan kesimpulan perilaku.

## Kesimpulan

Dataset synthetic tidak merepresentasikan pola kalender kerja apa pun (seragam-acak). Data real terlalu kecil dan terlalu banyak noise pengujian untuk menjadi baseline kalender. Validasi terhadap kalender kerja resmi membutuhkan data operasional yang lebih panjang + sumber tanggal merah (saat ini UNKNOWN — lihat 25_holiday_analysis.md).
