# 14 — Laporan Baseline Dataset Audit Log

Tanggal: 2026-08-23 · Commit `b9857fc1` · Semua angka berasal dari audit READ-ONLY (skrip di folder ini) atau query SELECT-only.

## 1. Dataset apa yang sebenarnya tersedia?

| # | File | Baris x Kolom | Peran |
|---|---|---|---|
| 1 | `ai-service/dataset/generator/raw/audit_log_dataset.csv` | 15.000 x 13 | dataset utama, raw synthetic |
| 2 | `ai-service/dataset/preprocessed/X_train.npy` | 15.000 x 9 (float64) | matriks training VAE aktif |
| 3 | `ai-service/dataset/retraining/retraining_dataset_combined_raw.csv` | 15.329 x 14 | artefak lama (gabungan) |
| 4 | `ai-service/dataset/retraining/retraining_dataset_canonical.csv` | 15.329 x 12 | artefak lama (kanonik) |
| 5 | `ai-service/dataset/retraining/X_train_candidate.npy` | 9.680 x 9 (float32) | artefak lama (kandidat, tak terpakai) |
| 6 | `ai-service/dataset/dataset_vae.csv` | 25 x 10 | sampel legacy, skema berbeda |
| 7 | `ai-service/dataset/processed/{train,validation,test}.csv` | 0 baris (0 byte) | placeholder kosong |
| - | tabel PostgreSQL `audit_log` | 337 x 13 | sumber data real live |

## 2–4. Mana synthetic / real / yang dipakai VAE?

- **Synthetic**: file #1 (100% dibangkitkan generator seed 42; elemen "real" hanya daftar user dari DB dev saat generator dijalankan).
- **Real**: tabel `audit_log` (337 baris per tanggal audit); cuplikannya hanya masuk artefak gabungan #3–#5.
- **Dipakai VAE produksi**: hanya #1 → #2 → model `models/vae_model.pth` + threshold `models/deployment_config.json`. Artefak Stage 5 (#3–#5) tidak dipakai pipeline mana pun (tidak ada kode yang membacanya).

## 5. Bagaimana dataset dibuat?

Synthetic dibangkitkan `dataset/generator/generate_dataset.py`: workflow aktivitas per role (`flows.py`), timestamp acak tahun 2025 antara 07:00–17:00 dengan rantai sesi +10–180 detik, IP/device tetap per profil user yang dibaca live dari tabel `users`, anomali disuntikkan dengan mutasi field (`anomaly.py`), label ground-truth `anomaly_type`/`risk_level` tersimpan lalu didrop saat preprocessing. Data real berasal dari penulisan otomatis backend (`auditLogService`) ke tabel `audit_log`.

## 6. Jumlah record

15.000 synthetic · 337 real live · 15.329 gabungan lama · 25 legacy sample · X_train aktif 15.000 baris.

## 7–8. Rentang waktu & distribusi jam (synthetic utama)

- Rentang: **2025-01-01 03:22:26 s/d 2025-12-31 16:34:24** (365 tanggal, tanpa hari kosong; timestamp tanpa timezone).
- Per jam: 00–06 = 57–78/jam (total 450, seluruhnya label `login_luar_jam`) · 07–16 = 1.368–1.527/jam · 17 = 53 · 18–23 = 0.
- Bucket (laporan faktual, bukan label anomali): `<08:00` = 1.854 (12,36%) · `08:00–15:59` = 11.633 (77,55%) · `>=16:00` = 1.513 (10,09%).
- Real live: rentang 2026-07-05 s/d 2026-08-19; aktivitas malam signifikan (jam 0 = 51; jam 22 = 42) mengindikasikan proses otomatis/pengujian.

## 9. Distribusi hari

Weekday 10.802 event (72,01%) vs weekend 4.198 (27,99%) — proporsi seragam-acak generator. Status tanggal merah: **UNKNOWN** untuk seluruh baris (tidak ada sumber kalender di repository).

## 10. Distribusi aktivitas & label (synthetic)

Login 23,97% · Logout 23,97% · Lihat Perkara 23,31% · Cari Berkas 21,57% · Lihat Berkas / Input Berkas / Verifikasi masing-masing 1,74% · Dashboard / Kelola User / Kelola Kode Klasifikasi masing-masing 0,65%. Status: Berhasil 97%, Gagal 3%. Label ground-truth: Normal 90%; login_luar_jam 3%; ip_berubah 2%; device_berubah 1,5%; aktivitas_terlalu_cepat 1,2%; durasi_tidak_wajar 1%; peminjaman_massal 0,8%; verifikasi_massal 0,5%.

Real live (337): LOGIN_SUCCESS 62 · ACCESS_BERKAS_FILE 40 · LOGOUT 29 · sisanya tersebar pada 30 aksi lain; role Admin mendominasi (traffic uji).

## 11. Kondisi file/path/hash

Tidak ada satu pun atribut file/path/hash/checksum/ukuran pada ketiga dataset CSV (dinyatakan eksplisit di 11_file_integrity_audit.csv). Rantai hash SHA-256 hanya ada di tabel `audit_log`: 337 entri, 0 hash invalid, 1 NULL `hash_sebelumnya` (baris pertama rantai).

## 12. Masalah dataset

1. Empat fitur VAE (duration_ms, object_count, device, ip_address) bernilai default/unknown pada seluruh data real → tidak punya dasar empiris.
2. Aktivitas modul Peminjaman, keamanan akun, dan sarana tidak terwakili di synthetic.
3. Profil waktu ditentukan parameter generator (07–17), bukan observasi; tidak ada pemodelan kalender.
4. Jalur preprocessing training vs inference berbeda (IP integer vs kategori+encoder kosong; numerik mentah vs log1p; jam lokal vs UTC→WIB).
5. Threshold = persentil-95 atas error data training itu sendiri; tidak ada train/validation/test split pada jalur aktif.
6. Dokumen desain lama (`docs/VAE_ARCHITECTURE.md`, laporan Stage 5) bertentangan dengan implementasi (10 vs 9 fitur; klaim localhost=329 yang sebenarnya mayoritas IP unknown).
7. Kredensial DB tertulis plaintext di `generator/config.py` dan `prepare_retraining_dataset.py` (temuan keamanan, dibiarkan apa adanya pada tahap audit).

## 13. Belum dapat dipastikan

- SOP resmi jam kerja 08.00–16.00 (dokumen tidak ada di repository).
- Daftar tanggal merah tahun mana pun (tidak ada sumber).
- Representativitas log real sebagai aktivitas operasional manusia (dominasi traffic uji).
- Nilai threshold aktual terhadap data unseen (belum pernah dievaluasi di luar data training).

## 14. Analisis tahap berikutnya

Lihat `30_candidate_dataset_rules.md` (Tahap 2): perbaikan pengisian IP/device/durasi di backend, penyelarasan kamus aktivitas, kalender kerja, split dataset, serta keputusan sumber data (regenerasi sintetis berbasis aturan baru vs akumulasi log operasional).
