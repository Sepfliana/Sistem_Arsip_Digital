# 32 — Narasi Akademik: Validasi Dataset terhadap SOP dan Kondisi Operasional

> Draf narasi untuk bahan skripsi. Semua pernyataan berdasarkan hasil audit Tahap 1–2 pada folder ini; tidak ada perubahan dataset yang diklaim.

## Sumber dataset

Sistem Informasi Arsip Berkas Perkara Kejaksaan Negeri Pariaman mencatat aktivitas pengguna pada tabel `audit_log` PostgreSQL yang dirantai secara kriptografis (kolom `hash_sebelumnya` dan `hash_entri`, SHA-256). Verifikasi menunjukkan rantai tersebut utuh: tidak ditemukan hash kosong atau tidak valid, dengan satu nilai `hash_sebelumnya` NULL yang merupakan baris pertama rantai. Namun, dataset yang saat ini digunakan untuk melatih Variational Autoencoder (VAE) **bukan** berasal dari tabel tersebut, melainkan dataset sintetis 15.000 baris hasil generator internal (`ai-service/dataset/generator/`) dengan seed acak 42. Elemen nyata satu-satunya dalam dataset sintetis adalah daftar pengguna yang dibaca dari basis data pengembangan pada saat pembangkitan (72 pengguna unik, termasuk akun uji).

## Perbedaan synthetic dan real

Data real berjumlah 337 baris (5 Juli–19 Agustus 2026) dan bersifat sangat kecil serta didominasi aktivitas non-operasional: 333 dari 337 baris memiliki `ip_address` dan `device` bernilai 'unknown', tiga baris tercatat dengan User-Agent axios (indikasi skrip otomatis), dan sebagian besar `durasi_ms` serta `jumlah_objek` berada pada nilai default (0 dan 1). Sebaliknya, dataset sintetis menyajikan variasi kaya pada atribut yang sama (durasi 1–106.760 ms; objek 1–200; sembilan jenis perangkat; alamat IP internal dan publik). Artinya, empat fitur yang justru menjadi masukan VAE — durasi, jumlah objek, perangkat, dan alamat IP — sepenuhnya merupakan konstruksi generator tanpa padanan empiris pada log operasional.

## Hubungan dataset dengan SOP

Dokumen SOP tidak ditemukan di dalam repository sehingga validasi dilakukan terhadap bukti source code dan log aktual. Dari sepuluh aktivitas sintetis, tujuh memiliki padanan pada aksi yang benar-benar dicatat backend (Login/Logout, akses dan kelola berkas, verifikasi, kelola user), sedangkan tiga — Dashboard, Lihat Perkara, dan Kelola Kode Klasifikasi — tidak pernah terekam oleh sistem logging manapun. Sebaliknya, seluruh siklus Peminjaman, proses keamanan akun (2FA dan reset kata sandi), pengelolaan lemari/rak, serta retensi arsip hadir di log real namun sama sekali tidak direpresentasikan dalam dataset latihan.

## Kondisi jam kerja, weekend, dan tanggal merah

Generator menggunakan jendela waktu 07.00–17.00 (parameter `WORK_START=7`, `WORK_END=17`), menghasilkan distribusi 77,55% aktivitas pada pukul 08.00–15.59, 9,36% pada 07.00–07.59, dan 9,73% pada 16.00–16.59. Tanggal dipilih seragam-acak sehingga weekend menampung 27,99% aktivitas — proporsi yang tidak membedakan hari kerja maupun hari libur. Pada data real, hanya 40,65% aktivitas jatuh pada pukul 08.00–15.59 dan 31,16% terjadi pada akhir pekan, konsisten dengan dominasi trafik pengujian di luar jam kerja. Tidak ada sumber kalender tanggal merah di dalam project, sehingga status hari libur seluruh baris dilaporkan UNKNOWN; daftar libur tidak direkonstruksi untuk menghindari fabrikasi. Sesuai batasan analisis, aktivitas di luar jam kerja, weekend, maupun tanggal merah tidak diberi label anomali pada tahap ini.

## Hasil validasi dan gap

Validasi menyimpulkan bahwa dukungan data operasional terhadap dataset sintetis terbatas pada jenis aktivitas inti dan struktur peran (Admin/Arsiparis/User). Gap terbesar adalah: (1) atribut teknis (IP, device, durasi, jumlah objek) yang tidak diisi aplikasi sehingga mustahil divalidasi; (2) absennya modul Peminjaman dan keamanan akun dari dataset latihan; (3) profil waktu yang ditentukan parameter generator alih-alih observasi; (4) ketiadaan dokumen SOP dan sumber kalender sebagai acuan. Rincian setiap gap beserta tingkat keyakinannya tersedia pada `29_dataset_gap_analysis.csv`.

## Penutup

Temuan-temuan di atas merupakan baseline kondisi awal. Rekomendasi aturan dataset untuk tahap perbaikan telah dirancang secara tentatif pada `30_candidate_dataset_rules.md` dan belum diterapkan: selama tahap validasi ini tidak ada record yang diubah, dihapus, digabung, ataupun dilabeli ulang.
