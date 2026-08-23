# 40 — Logika Temporal Generator Dataset Synthetic

Berdasarkan penelusuran source code `ai-service/dataset/generator/` (`config.py`, `utils.py`, `simulator.py`, `flows.py`, `anomaly.py`, `user_profile.py`). Generator tidak diubah.

## Metode pembentukan waktu (kesimpulan utama)

Kombinasi **random uniform + fixed range + session chain**:

1. **Fixed range**: tahun tetap 2025 (`YEAR`); jam dibatasi jendela `[WORK_START=7, WORK_END=17)` (`config.py`).
2. **Random uniform**: tanggal dipilih seragam-acak dari seluruh 365 hari 2025; jam/menit/detik dipilih acak di dalam jendela tersebut (`utils.py::random_date/random_time`). Tidak ada bobot distribusi (bukan normal/poisson).
3. **Session chain**: satu sesi pengguna menjalankan rangkaian aktivitas workflow (`flows.py`) — timestamp aktivitas berikutnya = sebelumnya + gap acak. Hasil audit empiris: gap minimum 10 detik, median 100 detik, maksimum ±16 jam (57747 s).
4. **Anomali injection** menimpa waktu secara khusus: `login_luar_jam` memakai jam seragam `[0, 6]` (`anomaly.py`), sisanya tetap dalam jendela normal.

## Jawaban atas tujuh pertanyaan audit

| # | Pertanyaan | Jawaban | Bukti |
|---|---|---|---|
| 1 | Sengaja menghasilkan weekend? | **Tidak ada konsep weekend sama sekali** — weekend muncul sebagai efek samping tanggal seragam-acak (proporsi teoretis 2/7 = 28,57%; aktual 27,99%) | `utils.py` tidak menyaring day-of-week; 35_weekday_distribution.csv |
| 2 | Sengaja menghasilkan tanggal merah? | **Tidak** — tidak ada daftar libur/kalender di generator | grep holiday/libur/kalender = nihil |
| 3 | Konsep working day? | **Tidak ada** — hanya batas tahun dan jam | `config.py` |
| 4 | Konsep working hour? | **Ada**, berupa fixed range 07.00–17.00 (bukan 08.00–16.00) | `WORK_START`/`WORK_END` |
| 5 | Timestamp berdasarkan role? | **Tidak langsung** — role hanya menentukan workflow/jumlah langkah; distribusi jam sama untuk semua role | `flows.py`; 09_actor_distribution.csv Tahap 1 |
| 6 | Timestamp mengikuti session? | **Ya** — aktivitas berantai dalam satu session_id | `simulator.py`; statistik gap sesi |
| 7 | Dependency antaraktivitas? | **Ya, intra-sesi saja** (gap acak antar langkah); antar-sesi independen | statistik gap 10 s – 57747 s |

## Implikasi audit

Pola timestamp dataset sepenuhnya **turunan parameter generator** (fixed range + uniform random + chain), bukan observasi operasional. Ditandai sebagai *temporal characteristic*, bukan anomali. Angka pendukung: tidak ada satu pun record tepat 07:00:00 atau 17:00:00 (interval setengah-terbuka), nol aktivitas jam 18–23, dan seluruh 450 record <07.00 adalah label `login_luar_jam`.
