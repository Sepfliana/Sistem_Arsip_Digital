# 18 — Analisis Perilaku Generator Synthetic

Bukti: `ai-service/dataset/generator/{generate_dataset,flows,anomaly,simulator,utils,user_profile,activity_profile,db_loader,config}.py`. Read-only; generator tidak diubah.

| # | Pertanyaan | Jawaban faktual | Bukti |
|---|---|---|---|
| 1 | Bagaimana timestamp dibuat? | Tanggal acak tahun 2025 (offset 0–364 hari dari 2025-01-01), lalu detik acak dalam [07:00:00, 17:00:00]; aktivitas berikutnya dalam sesi +10–180 detik. Naik kelas timestamp (tanpa timezone). Diurutkan ascending sebelum ditulis. | `utils.py:7-10,25-26`; `generate_dataset.py:84,90` |
| 2 | Bagaimana tanggal dibuat? | Seragam-acak sepanjang 2025 — setiap tanggal memiliki aktivitas; tidak ada pembobotan hari kerja vs libur. | `utils.py:8-9` |
| 3 | Bagaimana jam dibuat? | Hanya dari `WORK_START*3600` s/d `WORK_END*3600` detik (=07:00–17:00). Anomali `login_luar_jam` mengganti jam menjadi 0–6. Efek samping: menit/detik seragam; jam 17 hampir tidak terisi (53 baris) karena start maksimal tepat 17:00:00 dan hanya bertambah via rantai sesi. | `config.py:13-14`, `utils.py:10`, `anomaly.py:19-20` |
| 4 | Bagaimana aktivitas dibuat? | Workflow tetap per role (`WORKFLOWS`): Admin 5 langkah, Arsiparis 6, User 4; sesi dibangun utuh per login. Tidak ada aktivitas Peminjaman sama sekali. | `flows.py`, `simulator.py` |
| 5 | Bagaimana role/user dibuat? | Daftar user aktif (Admin/Arsiparis/User) dibaca LIVE dari tabel `users`+`roles` PostgreSQL saat generator dijalankan → 72 user unik (termasuk akun uji seperti `audit_arsiparis_e2e`). Profil user dipilih acak per sesi. | `db_loader.py:13-24`, `generate_dataset.py:37-42` |
| 6 | Bagaimana device dibuat? | Satu device acak per profil user dari {Windows, Laptop Windows, PC Windows, Android, iPhone}; anomali `device_berubah` mengganti dengan {Linux, MacOS, Unknown Device, Virtual Machine}. | `user_profile.py:10`, `utils.py:37-42`, `anomaly.py:25-27` |
| 7 | Bagaimana IP dibuat? | Satu IP internal `192.168.1.<2-254>` per profil user; anomali `ip_berubah` mengganti dengan IP publik dari prefix generator (8.,20.,36.,45.,66.,103.,114.,139.,157.,180.). | `config.py:22-26`, `utils.py:13-18`, `anomaly.py:22-23` |
| 8 | Bagaimana normal behavior dibuat? | status="Berhasil", risk_level="Normal", anomaly_type="Normal"; durasi & jumlah objek diambil dari rentang per aktivitas (`ACTIVITY_PROFILE`: durasi 200–12000 ms, objek 1–10); 3% baris beraktivitas {Login, Verifikasi, Input Berkas, Peminjaman} dipilih acak menjadi "Gagal" — catatan: "Peminjaman" tak pernah ada sehingga efektif hanya Login/Verifikasi/Input Berkas yang bisa gagal. | `generate_dataset.py:45-59`, `activity_profile.py` |
| 9 | Bagaimana anomaly dibuat? | Disuntikkan pasca-generasi pada 10% baris (1.500): 450 login_luar_jam (jam→0–6), 300 ip_berubah, 225 device_berubah, 180 aktivitas_terlalu_cepat (durasi→1–100 ms), 150 durasi_tidak_wajar (durasi×5–10), 120 peminjaman_massal (object_count→30–100), 75 verifikasi_massal (object_count→50–200). Anomali non-login dipilih dari SEMUA baris tanpa memandang jenis aktivitasnya. | `generate_dataset.py:62-78`, `anomaly.py:12-39`, `config.py:31-38` |
| 10 | Bagaimana label anomaly_type dibuat? | Ditulis eksplisit saat injeksi (`event["anomaly_type"] = anomaly`); "Normal" untuk sisanya. Label ini DIDROP oleh preprocessing — tidak pernah masuk VAE. | `anomaly.py:18`, `preprocessing.py:48-50` |
| 11 | Bagaimana risk_level dibuat? | Fungsi jenis anomali: login_luar_jam/ip_berubah/device_berubah→Low; durasi/terlalu_cepat→Medium; massal→High; normal→"Normal". Juga DIDROP. Konsistensi label-risk terverifikasi 100% (05_quality_audit.csv). | `anomaly.py:21,24,27,30,33,36,39` |
| 12 | Mempertimbangkan hari kerja? | **TIDAK** — tanggal murni acak; Senin–Minggu sama probabelnya. | `utils.py:8-9` |
| 13 | Mempertimbangkan weekend? | **TIDAK** — tidak ada pembeda apa pun untuk Sabtu/Minggu (hasil: 28% event jatuh di weekend). | idem + hasil audit 22_weekday_comparison.csv |
| 14 | Mempertimbangkan tanggal merah? | **TIDAK** — tidak ada referensi kalender/libur di seluruh kode generator. | grep "libur/holiday/tanggal merah" = nihil |
| 15 | Mempertimbangkan jam kerja 08.00–16.00? | **TIDAK sesuai parameter tersebut** — generator memakai jendela 07:00–17:00 (`WORK_START=7, WORK_END=17`), bukan 08:00–16:00. Distribusi hasil: 07–07:59 = 9,36%; 16–16:59 = 9,73%. | `config.py:13-14` |

## Implikasi faktual (tanpa mengubah apa pun)

1. Seluruh karakteristik temporal dataset berasal dari asumsi generator, bukan pengamatan operasional.
2. Anomali sintetis didefinisikan berdasarkan aturan yang sama dengan generator (jam <07, IP eksternal, dsb.) — model belajar membedakan "aturan generator", bukan perilaku manusia nyata.
3. Aktivitas inti modul Peminjaman (AJUKAN/SETUJUI/TOLAK/PINJAM/PENGEMBALIAN) tidak direpresentasikan meskipun ada di aplikasi & log real.
