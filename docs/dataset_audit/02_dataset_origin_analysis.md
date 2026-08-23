# 02 — Analisis Asal-Usul Dataset (Origin Analysis)

Tanggal audit: 2026-08-23 · Metode: penelusuran source code + statistik file (READ-ONLY) · Commit: `b9857fc1`

## Peta Sumber → Generator/DB → Dataset → Preprocessing → Model

```
[A] JALUR SYNTHETIC (AKTIF - dipakai VAE produksi)
    users PostgreSQL (db_loader.py, SELECT aktif saja)
      └─> dataset/generator/generate_dataset.py  (random.seed=42)
            └─> dataset/generator/raw/audit_log_dataset.csv   [15.000 baris]
                  └─> preprocessing.py
                        ├─ LabelEncoder: activity, status, device
                        ├─ ip_address -> integer (ipaddress.ip_address)
                        ├─ StandardScaler (9 fitur)
                        └─> dataset/preprocessed/X_train.npy [15000x9 float64]
                              ├─> train_vae_pytorch.py -> models/vae_model.pth
                              └─> services/inference.py -> models/deployment_config.json (threshold)

[B] JALUR GABUNGAN SYNTHETIC+REAL (artefak lama Stage 5, TIDAK dipakai pipeline aktif)
    dataset/generator/raw/audit_log_dataset.csv (15.000)
    + SELECT * FROM audit_log ORDER BY id ASC  (329 baris saat ekstraksi; 337 saat audit ini)
      └─> prepare_retraining_dataset.py (Stage 5)
            ├─ normalisasi via utils/preprocessing_contract.py (canonical mapping)
            └─> dataset/retraining/retraining_dataset_combined_raw.csv [15.329]
            └─> dataset/retraining/retraining_dataset_canonical.csv   [15.329 x 12 kolom]
            └─> dataset/retraining/X_train_candidate.npy [9680x9] + candidate_scaler.pkl + candidate_encoders.pkl

[C] TABEL LIVE audit_log PostgreSQL (sumber data real operasional)
    ditulis oleh backend (auditLogService) untuk setiap aksi mutasi/login
    kolom integritas: hash_sebelumnya, hash_entri (SHA-256 chaining)
```

## A. Dataset Synthetic — `dataset/generator/raw/audit_log_dataset.csv`

**Generator**: `ai-service/dataset/generator/generate_dataset.py` + modul pendukung.

| Parameter | Nilai | Bukti |
|---|---|---|
| Jumlah record target | 15.000 (`TOTAL_ROWS`) | `generator/config.py:9` |
| Random seed | 42 (`RANDOM_SEED`, `random.seed()` di `run()`) | `config.py:11`, `generate_dataset.py:81` |
| Rasio normal/anomali | 90% / 10% (`NORMAL_RATIO`/`ANOMALY_RATIO`) | `config.py:28-29` |
| Distribusi anomali | login_luar_jam 30%, ip_berubah 20%, device_berubah 15%, aktivitas_terlalu_cepat 12%, durasi_tidak_wajar 10%, peminjaman_massal 8%, verifikasi_massal 5% | `config.py:31-38` |
| Rentang timestamp | tahun 2025, detik acak antara 07:00:00–17:00:00 (`WORK_START=7`, `WORK_END=17`); sesi berlanjut +10–180 s per aktivitas | `utils.py:7-10`, `utils.py:25-26` |
| Aktivitas per role | Admin: Login→Dashboard→Kelola User→Kelola Kode Klasifikasi→Logout; Arsiparis: Login→Lihat Perkara→Lihat Berkas→Input Berkas→Verifikasi→Logout; User: Login→Lihat Perkara→Cari Berkas→Logout | `flows.py` |
| User | diambil LIVE dari tabel `users` PostgreSQL saat generator dijalankan (user aktif role Admin/Arsiparis/User) → 72 user unik, termasuk akun uji (mis. `audit_arsiparis_e2e`) | `db_loader.py:13-24`, hasil audit 09_actor_distribution |
| IP internal | `192.168.1.<2-254>` tetap per profil user | `utils.py:13-14`, `user_profile.py:11` |
| IP eksternal (anomali) | prefix dari daftar `EXTERNAL_IP_PREFIXES` (8., 20., 36., …) | `config.py:23-26`, `anomaly.py:23` |
| Device normal | {Windows, Laptop Windows, PC Windows, Android, iPhone}, tetap per profil user | `utils.py:37-38` |
| Device anomali | {Linux, MacOS, Unknown Device, Virtual Machine} | `utils.py:41-42` |
| Status | "Berhasil"; 3% sampel acak dari aktivitas {Login, Verifikasi, Input Berkas, Peminjaman} diubah jadi "Gagal" | `generate_dataset.py:54-59` |
| Durasi & objek | rentang per aktivitas dari `ACTIVITY_PROFILE` (durasi 200–12000 ms; objek 1–10) | `activity_profile.py` |
| Mekanisme anomali | mutasi field pada baris terpilih: jam→0–6 (login_luar_jam), IP→eksternal, device→anomali, durasi×5–10 atau 1–100 ms, object_count→30–100 / 50–200; risk_level diset Low/Medium/High sesuai jenis | `anomaly.py:12-39` |
| Label ground-truth | kolom `anomaly_type` + `risk_level` (keduanya DIDROP sebelum training) | `preprocessing.py:48-50` |
| Urutan baris | diurutkan asc berdasarkan timestamp setelah generasi | `generate_dataset.py:84` |

**Kesimpulan**: dataset ini 100% sintetis/simulasi. Elemen "real"-nya hanya daftar user yang dibaca dari database pengembangan saat generator dieksekusi.

## B. Dataset Gabungan (Stage 5) — artefak lama

Dibuat oleh `prepare_retraining_dataset.py`: menggabungkan 15.000 baris synthetic + 329 baris `SELECT * FROM audit_log` (ekstraksi READ-ONLY saat itu). Tujuan dokumen lama: menyiapkan kandidat retraining agar pola Localhost terwakili. **Tidak pernah dilanjutkan ke retraining** — model produksi (`models/vae_model.pth`, mtime 2026-07-28) lebih tua dari artefak kandidat (`X_train_candidate.npy`, mtime 2026-08-16) dan tidak ada skrip yang memuat artefak kandidat.

Kolom label (`is_anomali`, `risk_level_source`, `candidate_type`) ada di `combined_raw` tetapi tidak masuk `canonical` (hanya metadata pelengkap: source_type, source_id, candidate_type).

## C. Data Real Operasional — tabel `audit_log`

- Struktur: `database/schema.sql:126-140` — 13 kolom termasuk rantai hash `hash_sebelumnya`/`hash_entri`.
- Kondisi saat audit (query SELECT-only): **337 baris**, rentang `2026-07-05 17:09:56` s/d `2026-08-19 18:57:06`, 7 user unik.
- **IP address: 333/337 (98,8%) bernilai `'unknown'`; sisanya `::ffff:127.0.0.1` (3) dan `::1` (1)** — tidak ada satu pun IP klien publik/private terekam.
- **Device: 333/337 `'unknown'`**; sisanya User-Agent `axios/1.18.1` (3 — indikasi traffic skrip otomatis/test) dan UA Chrome/Electron asli (1).
- Status: `SUCCESS` (333), `VALID` (4) — kosakata berbeda dari synthetic (`Berhasil`/`Gagal`).
- Aksi: 33 nilai distinct bergaya `UPPER_SNAKE_CASE` (mis. `LOGIN_SUCCESS`, `CREATE_BERKAS`) — berbeda dari kamus synthetic (`Login`, `Input Berkas`, …).
- Aktivitas jam 00:00–02:00 dan 20:00–23:00 signifikan (51+11+7+22+42+25 = 158 event malam) → konsisten dengan traffic otomatis/seeder/test, bukan semata aktivitas manusia.
- Hash chain utuh: 0 `hash_entri` invalid/null; 1 `hash_sebelumnya` NULL (baris pertama rantai — wajar).

**Jawaban atas "apakah data real benar-benar log audit operasional?"**: tabel memang audit log aplikasi, tetapi isinya didominasi aktivitas pengembangan/pengujian (device unknown, UA axios, aktivitas tengah malam) sehingga **belum dapat dianggap representatif sebagai log operasional Kejaksaan**.
