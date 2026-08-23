# 66 — Spesifikasi Before/After Dataset (SPESIFIKASI — BELUM DITERAPKAN)

| Field | Current Condition | Target Condition | Transformation | Evidence |
|---|---|---|---|---|
| timestamp | 15.000 baris 2025, jendela 07–17, uniform-acak | TIDAK BERUBAH (v1). v2 (regenerasi): timestamp baru dengan profil waktu terkalibrasi + metadata kalender | NONE pada existing; regenerasi terpisah bila disetujui | 40; baris 1 matriks |
| activity | 10 aktivitas gaya UI Indonesia | Kamus = aksi backend yang benar-benar terlog (+ keluarga integritas & peminjaman & 2FA); pemetaan kanonik terdokumentasi | Regenerasi v2 / artefak pemetaan; bukan rename pada file existing | baris 11–17; 50 |
| status | Berhasil/Gagal | Tetap di synthetic + pemetaan ke SUCCESS/GAGAL kanonik | Pemetaan kontrak (sudah berjalan di inference) — didokumentasikan resmi | baris 20; 50 |
| role/workflow | 3 role × workflow terbatas | Diperluas: workflow Peminjaman, 2FA, lemari/rak, retensi sesuai role aktual backend | Regenerasi v2 | baris 13–15 |
| ip_address | 192.168.x.x sintetis; real 'unknown' | Synthetic tetap; REAL baru: IP klien asli hasil middleware | Perubahan di aplikasi (bukan dataset); tanpa imputasi | baris 22; 58 |
| device | 9 jenis sintetis; real 'unknown'/axios | Real baru: User-Agent asli dari klien resmi | Perubahan di aplikasi/klien | baris 21 |
| duration_ms | Sintetis 1–106.760 ms; real semua 0 | Real baru: durasi terukur middleware | Perubahan di aplikasi | baris 23 |
| object_count | Sintetis 1–200; real semua 1 | Real baru: jumlah objek faktual per transaksi | Perubahan di aplikasi | baris 24 |
| target_tipe/target_id | Absen di synthetic | Ditambahkan sebagai kolom kategorikal/referensi pada v2 | Regenerasi v2 | baris 29; 51/58 |
| file/path/hash | Absen di kedua dataset log; ada di tabel berkas | TETAP di integrity subsystem; tidak masuk fitur VAE; boleh jadi atribut pendukung non-fitur | NONE pada dataset latihan | baris 26–28 |
| label anomaly_type/risk_level | Ada di CSV, dibuang preprocessing | TETAP dipisah; hanya evaluasi; dokumentasi eksplisit batasan in-sample | NONE (status quo dipertahankan) | baris 32 |
| missing values | 0% synthetic; NULL kepala rantai real | NULL kepala rantai dibiarkan sah; tidak ada imputasi | NONE | baris 37 |
| duplikat | Belum discan persis | Scan dedup persis dijalankan dulu (verifikasi), hasil dilaporkan sebelum keputusan | Verifikasi-only Tahap 6 | baris 38 |
| fungsi dataset | Synthetic=training; real tak terpakai model | Synthetic=training v1; real=external validation/behavioral/schema reference | Deklarasi metodologis (dokumen) | baris 30–31 |

Target condition di atas adalah SPESIFIKASI untuk Tahap 6 dan tahap lanjutan — tidak satu pun yang diterapkan pada berkas dataset saat dokumen ini dibuat.
