# 132 — Tabel Skripsi: Proses Encoding & Scaling (Tahap 9)

Alur: **Dataset hasil feature engineering (Stage 8, 15.000×9 pra-encoding)**
→ **encoding kategorikal** (LabelEncoder activity/status/device; IP→integer 32-bit;
user_id/numerik passthrough) → **transformasi numerik** (tanpa log1p — mengikuti
kontrak training existing) → **scaling** (StandardScaler fit pada dataset sumber
training, parameter tersimpan) → **dataset numerik intermediate Stage 9
(15.000×9 float64)**.

| Tahap proses | Uraian singkat utk skripsi |
|---|---|
| Encoding kategorikal | Tiga kolom nominal diubah ke integer deterministik (urutan alfabetis). Mapping: activity 10 kelas (0–9), status biner (Berhasil=0, Gagal=1), device 9 kelas (0–8, termasuk Unknown Device sebagai kelas sah). |
| Encoding IP | Sesuai kontrak sistem existing, string IPv4 dikonversi ke bilangan bulat 32-bit (`ipaddress.ip_address`). Karakteristik: nilai terdistribusi tidak merata karena dominasi blok internal. |
| Passthrough numerik | user_id (identifier), duration_ms, object_count, hour (0–23), day_of_week (Senin=0…Minggu=6) dipertahankan numerik sesuai implementasi existing. |
| Scaling | StandardScaler per fitur (mean≈0, std≈1); parameter (mean_, scale_) disimpan untuk reproduksi dan pemakaian konsisten pada data lain. |
| Validasi output | 14/14 check PASS: seluruh sel numerik float64, tanpa NaN/Inf, urutan fitur deterministik, roundtrip decoder identik dengan label asal, jumlah baris tetap 15.000. |

**Penegasan**: hasil Tahap 9 adalah *dataset numerik intermediate* — **INI BELUM
FINAL VAE DATASET**. Final assembly (penamaan artefak produksi X_train, split,
kontrol leakage, sinkronisasi kontrak inference) adalah **TAHAP 10**, dan
keputusan penyelarasan representasi inference menyusul pada Tahap 11–12.
