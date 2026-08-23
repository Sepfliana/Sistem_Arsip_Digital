# 118 — Tabel Feature Engineering untuk Skripsi (Tahap 8)

Dataset: `audit_log_dataset_stage6.csv` (15.000 × 13).

| No | Kolom/Sumber | Jenis Data | Makna | Proses Feature Engineering | Output | Alasan |
|---|---|---|---|---|---|---|
| 1 | timestamp | datetime (WIB lokal) | Waktu kejadian aktivitas | Derivasi pasif: `dt.hour`, `dt.dayofweek`; kolom asli tidak masuk VAE | hour, day_of_week | Sumber fitur temporal; bukan fitur langsung |
| 2 | session_id | string ID | Pengelompokan alur kerja multi-event | Dipertahankan sebagai metadata konteks | — | Bukan perilaku per-event; 3.595 sesi |
| 3 | user_id | int identifier | Identitas pelaku aktivitas | Diklasifikasi kategorikal-nominal (pra-encoding) | user_id | Fitur perilaku; lihat catatan risiko ordinal |
| 4 | username | string | Nama akun | Dipisahkan sebagai referensi/identitas | — | Redundan dgn user_id; berisiko kebocoran identitas |
| 5 | role | kategori (3 nilai) | Peran pengguna | Metadata konteks, di luar kontrak 9 fitur | — | Kontrak sistem existing tidak memakainya |
| 6 | activity | kategori (10 nilai) | Jenis aktivitas UI | Representasi kategorikal nominal apa adanya (tanpa rename) | activity | Fitur perilaku inti |
| 7 | status | kategori biner | Hasil aksi Berhasil/Gagal | Validasi kosakata; siap utk encoding Tahap 9 | status | Sinyal anomali perilaku |
| 8 | ip_address | IPv4 string | Asal jaringan (internal/publik) | Konteks jaringan; representasi existing didokumentasikan (lihat 119/121) | ip_address | Behavioral/context feature |
| 9 | device | string (9 variasi) | Perangkat akses | Audit vocab; tanpa imputasi/fabrikasi | device | Behavioral context feature |
| 10 | duration_ms | integer | Durasi aktivitas ms | Statistik diaudit; CONTINUOUS BEHAVIORAL FEATURE | duration_ms | Sinyal durasi tidak wajar |
| 11 | object_count | integer | Jumlah objek tersentuh | Statistik diaudit; count behavioral | object_count | Sinyal aksi massal |
| 12 | risk_level | label teks | Label tingkat risiko generator | DIPISAHKAN sebagai ground truth | label | Tidak boleh jadi input VAE |
| 13 | anomaly_type | label teks (7 jenis) | Label jenis anomali sintetis | DIPISAHKAN sebagai ground truth | label | Evaluasi/analisis saja |

## Catatan per fitur kanonik

- **user_id**: semantiknya identifier kategorikal (72 unik), tetapi pipeline existing (training & inferensi) memperlakukannya numerik → risiko ordinal. Dicatat WARNING + CANDIDATE; tidak diubah.
- **activity**: 10 kosakata asli dipertahankan. Canonical mapping Tahap 6 = dokumentasi saja.
- **status**: `Berhasil` 14.550 / `Gagal` 450; biner hasil aksi.
- **device**: 9 variasi generator (PC Windows 4.088, Windows 3.393, Laptop Windows 3.057, iPhone 2.696, Android 1.541, Virtual Machine 68, Linux 57, MacOS 51, Unknown Device 49); missing condition = "Unknown Device" bawaan generator, bukan NaN.
- **ip_address**: 362 IP unik; internal 192.168.* = 14.700 baris, publik = 300. Training existing mengubah IP→integer penuh (metodologis, dicatat); kontrak inferensi memetakan ke kategori.
- **duration_ms**: min 1 / max 106.760 / mean 2.423,21 / median 1.495,5 / P25 894 / P75 3.475,25 / zero 0 → continuous behavioral.
- **object_count**: min 1 / max 200 / mean 4,44 / median 1 / zero 0 → count behavioral.
- **hour**: derivasi terverifikasi Δ=0; 18 jam unik (0–17).
- **day_of_week**: konvensi source code pandas `dt.dayofweek` → Senin=0 … Minggu=6; distribusi 0–6 lengkap (weekday 10.802, weekend 4.198 konsisten baseline).
