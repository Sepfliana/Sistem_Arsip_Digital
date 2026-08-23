# 42 — Perbandingan Temporal: Synthetic vs Data Real (Pembanding)

Sumber: `41_temporal_synthetic_vs_real.csv`. Dataset TIDAK digabung; real (337 record PostgreSQL) hanya pembanding.

## Distribusi jam

| Kategori | Synthetic | % | Real | % |
|---|---|---|---|---|
| <08:00 | 1.854 | 12,36% | 71 | 21,07% |
| 08:00–15:59 | 11.633 | 77,55% | 137 | 40,65% |
| 16:00–16:59 | 1.460 | 9,73% | 7 | 2,08% |
| >=17:00 | 53 | 0,35% | 122 | 36,20% |

## Hari

| Kategori | Synthetic | % | Real | % |
|---|---|---|---|---|
| WORKDAY | 10.802 | 72,01% | 232 | 68,84% |
| WEEKEND | 4.198 | 27,99% | 105 | 31,16% |

## Deskripsi perbedaan

1. **Konsentrasi jam kerja**: synthetic terkonsentrasi pada 08.00–15.59 (77,55%) sebagai konsekuensi jendela generator 07.00–17.00. Real lebih tersebar: hanya 40,65% di jam tersebut.
2. **Aktivitas malam**: real memiliki porsi besar >=17.00 (36,20%) dengan puncak pada jam 22–00 — konsisten dengan temuan Tahap 1 bahwa mayoritas trafik real adalah proses otomatis/pengujian (User-Agent axios, IP/device 'unknown'), bukan aktivitas manual kantor.
3. **Weekday/weekend**: proporsi WORKDAY vs WEEKEND kedua dataset relatif mirip (~69–72% vs ~28–31%), namun penyebabnya berbeda: synthetic karena tanggal seragam-acak tanpa konsep kalender; real karena trafik uji berjalan setiap hari termasuk akhir pekan.
4. **Tanggal merah**: tidak dapat dibandingkan langsung — rentang real (2026) berbeda tahun dari kalender 2025 synthetic; analisis holiday synthetic ada di `38_holiday_activity_analysis.md`.

## Interpretasi (dipisahkan dari fakta)

Perbedaan pola jam **tidak menyatakan salah satu dataset "salah"**. Keduanya mencerminkan proses pembentukannya masing-masing: parameter generator untuk synthetic; perilaku logging + trafik pengujian untuk real. Implikasinya bersifat metodologis: sebelum dipakai membandingkan/melatih model atas data operasional, perbedaan profil waktu ini perlu menjadi pertimbangan eksplisit (lihat `44_candidate_temporal_rules.md`).

Status kalender hari libur untuk data real 2026: **NEEDS_VERIFICATION** (di luar lingkup audit ini).
