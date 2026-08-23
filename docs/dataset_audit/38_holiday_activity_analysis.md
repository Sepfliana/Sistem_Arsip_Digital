# 38 — Analisis Aktivitas pada Tanggal Merah 2025

## Sumber kalender

Repository TIDAK memiliki daftar hari libur/kalender kerja/konfigurasi working day maupun dependency kalender (hasil penelusuran Tahap 1–2). Verifikasi dilakukan terhadap **sumber resmi eksternal**: SKB Menteri Agama, Menteri Ketenagakerjaan, dan Menteri PANRB Nomor 1017 Tahun 2024, No. 2 Tahun 2024, dan No. 2 Tahun 2024 tentang Hari Libur Nasional dan Cuti Bersama Tahun 2025, dipublikasikan oleh Sekretariat Kabinet RI (setkab.go.id, diakses 2026-08-23).

## Jumlah tanggal merah teridentifikasi

- **Libur nasional: 17 tanggal** · **Cuti bersama: 10 tanggal** · Total **27 tanggal** (lihat `37_holiday_calendar_audit.csv`).
- 4 dari 27 tanggal jatuh pada weekend (1 Jun, 17 Agu, 20 Apr, 29 Mar). Untuk matriks 39 digunakan precedence **HOLIDAY > WEEKEND > WORKDAY** (tanggal libur tetap diklasifikasi HOLIDAY meski bertepatan weekend).

## Aktivitas pada tanggal merah

| Indikator | Nilai |
|---|---|
| Total record pada 27 tanggal merah | **1.124** |
| Persentase dari 15.000 record | **7,4933%** |
| Pada jam kerja 08.00–15.59 | 874 (5,8267%) |
| Sebelum jam kerja (<08:00) | 145 (0,9667%) |
| Setelah jam kerja (>=16:00) | 105 (0,7000%) |

Semua 27 tanggal merah memiliki aktivitas (rentang 16–70 record/tanggal; tertinggi Hari Lahir Pancasila 1 Juni = 70, terendah Cuti Bersama Imlek 28 Januari = 16).

## Jenis aktivitas pada tanggal merah

Login 273 · Logout 273 · Lihat Perkara 269 · Cari Berkas 255 · Lihat Berkas / Input Berkas / Verifikasi @14 · Dashboard / Kelola User / Kelola Kode Klasifikasi @4. Label ground-truth pada tanggal merah: Normal 998; login_luar_jam 33; ip_berubah 25; durasi_tidak_wajar 19; aktivitas_terlalu_cepat 18; device_berubah 13; peminjaman_massal 11; verifikasi_massal 7.

## Aktivitas berdasarkan jam (tanggal merah)

Jam 07 = 112 · 08 = 143 · 09 = 94 · 10 = 130 · 11 = 120 · 12 = 105 · 13 = 93 · 14 = 98 · 15 = 91 · 16 = 101 · 17 = 4 · Jam 00–06 = 33 (seluruhnya label `login_luar_jam`).

## Catatan penting

Aktivitas pada tanggal merah **TIDAK dianggap anomali** pada audit ini — ia adalah karakteristik dataset sintetis akibat generator yang tidak memodelkan kalender. Interpretasi lebih lanjut ditunda ke tahap perbaikan (`44_candidate_temporal_rules.md`).
