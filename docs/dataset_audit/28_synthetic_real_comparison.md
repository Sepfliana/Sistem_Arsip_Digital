# 28 — Perbandingan Synthetic vs Real (Analisis)

Data mentah: `27_synthetic_real_comparison.csv`. Kedua dataset dianalisis terpisah, tidak digabung.

## 1. Skala & Cakupan

| Aspek | Synthetic | Real |
|---|---|---|
| Jumlah record | 15.000 | 337 |
| Rentang | 2025 penuh (365 hari) | 2026-07-05 s/d 2026-08-19 (~45 hari) |
| User unik | 72 | 7 |
| Jenis aktivitas | 10 (kamus Indonesia) | 33 (UPPER_SNAKE_CASE) |

## 2. Aktivitas: apa yang didukung data nyata?

Aktivitas synthetic yang memiliki padanan langsung di log real (lihat 19_activity_sop_validation.csv):

| Synthetic | Padanan real | Status dukungan |
|---|---|---|
| Login / Logout | LOGIN_SUCCESS / LOGOUT | SUPPORTED (kode + real) |
| Lihat Berkas / Cari Berkas | ACCESS_BERKAS_FILE | SUPPORTED |
| Input Berkas | CREATE_BERKAS, UPDATE_BERKAS | PARTIALLY_SUPPORTED |
| Verifikasi | VERIFIKASI_INTEGRITAS_BERKAS, EXPORT_VERIFICATION_REPORT | PARTIALLY_SUPPORTED |
| Kelola User | CREATE/UPDATE/DELETE_USER | SUPPORTED |
| **Dashboard** | tidak ada aksi logging-nya di kode maupun real | NOT_FOUND |
| **Lihat Perkara** | tidak ada aksi baca perkara di log | NOT_FOUND |
| **Kelola Kode Klasifikasi** | tidak ada aksi logging-nya | NOT_FOUND |

Sebaliknya, aktivitas real berikut TIDAK direpresentasikan sama sekali dalam synthetic: seluruh siklus Peminjaman (AJUKAN_PEMINJAMAN, SETUJUI/TOLAK_PEMINJAMAN, PINJAM, PENGEMBALIAN, UPDATE/DELETE_PEMINJAMAN), keamanan akun (SETUP_2FA_GENERATE, AKTIVASI_OTP, DISABLE_2FA_EMAIL_CHANGED, REQUEST_RESET_PASSWORD, RESET_PASSWORD), pengelolaan sarana (CREATE/UPDATE/DELETE_LEMARI, _RAK), dan operasi arsip lanjutan (RETENSI_INAKTIF, PERUBAHAN_STATUS_ARSIP, KEPUTUSAN_ANOMALI_*).

## 3. Dimensi temporal

| Bucket | Synthetic | Real |
|---|---|---|
| <07:00 | 3,00% (=450 label login_luar_jam) | 20,47% |
| 07:00–07:59 | 9,36% | 0,59% |
| **08:00–15:59** | **77,55%** | **40,65%** |
| 16:00–16:59 | 9,73% | 2,08% |
| >=17:00 | 0,35% | 36,20% |

Weekend: synthetic 27,99% vs real 31,16%. Hari libur: UNKNOWN keduanya.

Faktual: jendela jam generator (07–17) menghasilkan profil "77% di jam 08:00–15:59" yang tidak tercermin pada log real (41%), karena mayoritas event real berasal dari proses otomatis di luar jam kerja.

## 4. Atribut perilaku

| Atribut | Synthetic | Real | Dukungan nyata |
|---|---|---|---|
| duration_ms | 1–106.760 ms, variasi per aktivitas | **semua = 0** (default; aplikasi tidak mengukur durasi) | TIDAK ADA — fitur ini murni buatan generator |
| object_count/jumlah_objek | 1–200 (anomali massal sampai 200) | **semua = 1** (default) | TIDAK ADA |
| device | 5 device normal + 4 anomali | 'unknown' 333/337; axios UA ×3; Chrome/Electron ×1 | TIDAK ADA |
| ip_address | 192.168.1.x + prefix publik generator | 'unknown' 333/337; ::1 & ::ffff:127.0.0.1 ×4 | TIDAK ADA |
| status | Berhasil/Gagal | SUCCESS/VALID | setara secara semantik via mapping kanonik |
| hash/path file | tidak ada kolomnya | ada di tabel (hash chaining), tidak diekspor | sebagian (level DB saja) |

## 5. Kesimpulan

Perilaku synthetic yang memiliki dukungan data operasional nyata hanyalah **jenis aktivitas inti** (login/logout, akses & kelola berkas, verifikasi, kelola user) dan **struktur role** (Admin/Arsiparis/User). Sedangkan empat fitur numerik/kategorikal yang justru menjadi input VAE — `duration_ms`, `object_count`, `device`, `ip_address` — **tidak memiliki padangan nyata sama sekali**: nilai real semuanya default (0, 1, 'unknown'). Pola waktu synthetic juga dibentuk parameter generator (07–17), bukan observasi.

Implikasi metodologis (laporan saja): model VAE saat ini dilatih untuk mendeteksi penyimpangan dari distribusi buatan generator, sehingga hasil deteksi terhadap data real belum dapat disebut merepresentasikan anomali operasional.
