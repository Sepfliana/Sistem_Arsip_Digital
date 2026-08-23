# 45 — Tabel Skripsi: Audit Waktu dan Kalender Dataset

| No | Aspek | Metode Audit | Hasil | Interpretasi |
|---|---|---|---|---|
| 1 | Distribusi jam (12 interval) | Ekstraksi & agregasi kolom `timestamp` synthetic 15.000 record | Puncak 09.00–10.59 (≈10,2%/jam); 77,55% pada 08.00–15.59; 12,36% <08:00; 10,09% >=16:00 | Karakteristik jendela generator 07–17, bukan pola observasi |
| 2 | Aktivitas per tanggal | Agregasi harian 365 tanggal | Rata-rata 41,1; median 40; min 8 (2 Des); maks 90 (9 Okt) | Seragam-acak tanpa pola musiman |
| 3 | Hari dalam minggu | Agregasi day-of-week | Senin–Jumat 13,49–15,57%; Sabtu 13,65%; Minggu 14,33% | Generator tidak memiliki konsep hari kerja |
| 4 | Workday vs weekend | Klasifikasi Senin–Jumat vs Sabtu–Minggu | WORKDAY 72,01% · WEEKEND 27,99% | Weekend muncul efek samping acak, bukan disengaja |
| 5 | Verifikasi kalender 2025 | Penelusuran repository + verifikasi sumber resmi eksternal (setkab.go.id) | Repository tanpa kalender; SKB 2025 terverifikasi: 17 libur nasional + 10 cuti bersama | Kalender HOLIDAY dapat dipakai tanpa dikarang |
| 6 | Aktivitas pada tanggal merah | Join dataset dengan kalender terverifikasi | 1.124 record (7,49%) tersebar di seluruh 27 tanggal merah (16–70/tanggal) | Karakteristik generator; TIDAK diberi label anomali |
| 7 | Matriks hari × jam | Klasifikasi analitis 9 kombinasi | WORKDAY+WORKING 51,09%; WEEKEND+WORKING 20,63%; HOLIDAY+WORKING 5,83%; luar jam kerja total 22,45% | Peta temporal lengkap untuk baseline perbaikan |
| 8 | Logika temporal generator | Inspeksi source code generator | Fixed range + random uniform + session chain; seed 42; tanpa konsep weekend/libur/hari kerja | Pola waktu adalah turunan parameter, bukan observasi |
| 9 | Perbandingan dengan real (337 record) | Agregasi paralel tanpa penggabungan dataset | Jam kerja: synthetic 77,55% vs real 40,65%; >=17:00 real 36,20% (dominasi trafik uji) | Profil waktu berbeda karena proses pembentukan berbeda |
| 10 | Identifikasi masalah temporal | Analisis temuan berbasis bukti | 9 item issue (43_temporal_issue_analysis.csv); istilah characteristic/candidate issue | Semua masalah terdokumentasi dengan confidence |
| 11 | Baseline pra-perbaikan | Rekap angka audit | 47_temporal_baseline.md | Referensi wajib pembanding pasca-perbaikan |
