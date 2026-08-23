# 47 — Baseline Temporal Pra-Perbaikan (Dataset Synthetic 15.000 Record)

Angka wajib pembanding untuk menilai dataset sebelum vs sesudah tahap perbaikan. Semua dari audit Tahap 3 (sumber: `33`–`39`, `t3_stats.json`, `t3_holiday_stats.json`).

| Indikator | Nilai | Persentase |
|---|---|---|
| Total record | 15000 | 100% |
| Sebelum 08.00 (<08:00) | 1854 | 12,36% |
| Jam kerja 08.00–15.59 | 11633 | 77,5533% |
| >=16.00 | 1513 | 10,0933% |
| WORKDAY (Sen–Jum) | 10802 | 72,0133% |
| WEEKEND (Sab–Min) | 4198 | 27,9867% |
| HOLIDAY (27 tanggal SKB 2025) | 1124 | 7,4933% |
| Holiday unknown | 0 | 0% |
| Weekend + luar jam kerja | 924 | 6,16% |
| Holiday + luar jam kerja | 250 | 1,6667% |

Baseline sekunder:

- Rincian matriks: WORKDAY+WORKING 7664 (51,0933%) · WORKDAY+BEFORE 1215 (8,1%) · WORKDAY+AFTER 978 (6,52%) · WEEKEND+WORKING 3095 (20,6333%) · WEEKEND+BEFORE 494 (3,2933%) · WEEKEND+AFTER 430 (2,8667%) · HOLIDAY+WORKING 874 (5,8267%) · HOLIDAY+BEFORE 145 (0,9667%) · HOLIDAY+AFTER 105 (0,7%).
- Per interval jam: <07:00 = 450 · 07:00–07:59 = 1404 · tiap jam 08–15 = 1368–1527 · 16:00–16:59 = 1460 · >=17:00 = 53 · jam 18–23 = 0.
- Harian: 365 tanggal unik · rata-rata 41,0959 · median 40 · maks 90 (2025-10-09) · min 8 (2025-12-02).
- Label bawaan pada zona non-kerja: seluruh 450 record `<07:00` berlabel `login_luar_jam`; 0 record normal <07:00.

Catatan klasifikasi baseline: jendela jam kerja acuan 08.00–16.00 (SOP belum terverifikasi); kalender HOLIDAY = SKB 2025 terverifikasi; precedence HOLIDAY > WEEKEND > WORKDAY. Dataset asli tidak diubah — baseline ini mendefinisikan titik nol sebelum keputusan perbaikan apa pun.
