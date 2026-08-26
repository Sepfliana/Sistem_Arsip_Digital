# VAE Architecture Blueprint — Sistem Arsip Digital

Dokumen ini mendeskripsikan arsitektur Variational Autoencoder (VAE) untuk deteksi anomali audit log pada Sistem Arsip Digital. Dokumen ini awalnya dibuat sebagai blueprint Sprint 2 dan telah diperbarui agar sesuai dengan implementasi final.

## A. Tujuan Model

Model VAE dirancang untuk mempelajari pola aktivitas normal dari tabel `audit_log`, lalu mendeteksi aktivitas yang tidak normal berdasarkan reconstruction error.

Model ini hanya digunakan untuk anomaly detection pada audit log. Model tidak digunakan untuk prediksi kategori dokumen, identifikasi pengguna, autentikasi, atau malware detection.

## B. Input Model

Input model berasal dari hasil preprocessing pada `ai-service/utils/final_preprocessing_contract.py`.

Feature yang digunakan (9 fitur, urutan tetap):

| No | Feature | Sumber | Transformasi |
|---:|---|---|---|
| 1 | `user_id` | `audit_log.user_id` | Ordinal Encoding dari training data, lalu StandardScaler, lalu bounded z-score [-3, 3] |
| 2 | `activity` | `audit_log.aksi` | Activity mapping backend → label training, lalu Ordinal Encoding |
| 3 | `status` | `audit_log.status` | Status mapping backend → label training, lalu Ordinal Encoding |
| 4 | `device` | `audit_log.device` | Device normalization User-Agent → kelas training, lalu Ordinal Encoding |
| 5 | `ip_address` | `audit_log.ip_address` | IPv4 → unsigned 32-bit integer, lalu StandardScaler, lalu bounded z-score [-3, 3] |
| 6 | `duration_ms` | `audit_log.durasi_ms` | Durasi aktual operasi backend (ms), StandardScaler |
| 7 | `object_count` | `audit_log.jumlah_objek` | Jumlah objek yang diproses, StandardScaler |
| 8 | `hour` | `audit_log.waktu` | Ekstraksi jam (0-23) dari timestamp WIB |
| 9 | `day_of_week` | `audit_log.waktu` | Ekstraksi hari dalam minggu (0=Monday, 6=Sunday) dari timestamp WIB |

## C. Jumlah Input Feature

```text
FEATURE_COLUMNS = 9
```

Input layer dan output layer memiliki dimensi 9.

## D. Arsitektur Encoder

Encoder bertugas memetakan feature vector audit log ke latent space.

Arsitektur implementasi final:

```text
Input (9)
↓
Linear(9, 64)
↓
ReLU
↓
Dropout(0.2)
↓
Linear(64, 32)
↓
ReLU
↓
Latent Mean (8)

Latent Log Variance (8)
```

Encoder tidak menghasilkan kelas atau label. Encoder hanya menghasilkan representasi laten dari pola audit log.

Inference menggunakan deterministic posterior mean (`mu`), bukan sampling.

## E. Arsitektur Decoder

Decoder bertugas merekonstruksi kembali feature vector dari latent space.

Arsitektur implementasi final:

```text
Latent Space (8)
↓
Linear(8, 32)
↓
ReLU
↓
Linear(32, 64)
↓
ReLU
↓
Output (9)
```

Decoder harus menghasilkan output dengan jumlah dimensi yang sama dengan input, yaitu `9`.

## F. Output Layer

Output layer merekonstruksi feature audit log yang sudah diproses.

```text
Output dimension = 9
Activation = linear
```

Activation `linear` dipilih karena input akhir berupa nilai numerik hasil encoding dan scaling. Model harus bebas merekonstruksi nilai kontinu, bukan memetakan ke probabilitas kelas.

## G. Reconstruction Error

Reconstruction error mengukur selisih antara input asli dan hasil rekonstruksi decoder.

```text
feature_error[i] = (input[i] - reconstructed[i])²
```

Nilai error dihitung per-feature (9 nilai per record).

## H. Anomaly Score

Anomaly score merupakan rata-rata dari 9 squared reconstruction errors:

```text
anomaly_score = mean(feature_error[0], ..., feature_error[8])
```

Aktivitas normal diharapkan memiliki anomaly score rendah karena mirip dengan pola training. Aktivitas tidak normal diharapkan menghasilkan anomaly score lebih tinggi.

## I. Threshold

Threshold final menggunakan persentil ke-95 (P95) dari anomaly scores pada data training normal:

```text
threshold = P95(train_normal_anomaly_scores) = 1.6426611317633713
```

Threshold disimpan pada `ai-service/models/final_vae/threshold.json`.

## J. Feature Contribution

Kontribusi feature terhadap anomaly score dihitung sebagai rasio error per-feature terhadap total error:

```text
feature_contribution[i] = feature_error[i] / total_feature_error
```

Dimana `total_feature_error = sum(feature_error[0], ..., feature_error[8])`.

Total seluruh feature contribution = 1.0.

Sistem menyediakan:

- `feature_errors`: 9 nilai error per feature
- `feature_contributions`: 9 nilai kontribusi per feature (total = 1.0)
- `dominant_features`: 3 feature dengan kontribusi terbesar
- `explanation`: teks penjelasan anomaly score dalam Bahasa Indonesia

## K. Risk Categories

Tepat 3 kategori risiko berdasarkan anomaly score dan threshold:

| Kategori | Kondisi | Label Database |
|---|---|---|
| Normal | score ≤ 1.6426611317633713 | — |
| Perlu Ditinjau | 1.6426611317633713 < score < 1.5 × 1.6426611317633713 | SEDANG |
| High Risk | score ≥ 1.5 × 1.6426611317633713 | TINGGI |

Batas atas Perlu Ditinjau ≈ 2.463991697645057.

AI service menghasilkan level: `LOW`, `MEDIUM`, `HIGH`.

Backend menerjemahkan ke database: `HIGH` → `TINGGI`, `MEDIUM` → `SEDANG`.

Frontend menampilkan: Normal, Perlu Ditinjau, High Risk.

Status "Belum Dianalisis" adalah status tampilan untuk record yang belum dianalisis, bukan kategori risiko.

## L. Rekomendasi Hyperparameter

| Hyperparameter | Nilai | Alasan |
|---|---:|---|
| Latent Dimension | `8` | Cukup kecil untuk memaksa kompresi pola audit log, tetapi mampu merepresentasikan variasi aktivitas. |
| Hidden Layers | `[64, 32]` encoder dan `[32, 64]` decoder | Ukuran ringan untuk tabular audit log. |
| Activation Function | `relu` | Cocok untuk dense layer tabular dan menangkap pola non-linear. |
| Output Activation | `linear` | Output merekonstruksi feature numerik kontinu. |
| Optimizer | `adam` | Baseline stabil untuk training neural network tabular. |
| Learning Rate | `0.001` | Default optimizer Adam, baseline stabil. |
| Epoch | `100` | Batas atas training. |
| Dropout | `0.2` | Mengurangi overfitting pada pola aktivitas berulang. |
| KL Capacity Target | `0.5` | Target KL divergence capacity. |
| KL Capacity Warmup | `60` | Epoch warmup sebelum capacity mencapai target. |
| Random Seed | `42` | Reproduksibilitas. |

## M. Desain Loss Function

Loss function VAE terdiri dari dua komponen utama dan satu komponen capacity annealing.

### Reconstruction Loss

```text
reconstruction_loss = mean_squared_error(input_vector, reconstructed_vector)
```

### KL Divergence

```text
kl_divergence = -0.5 * sum(1 + log_variance - mean^2 - exp(log_variance))
```

### KL Capacity Annealing

VAE menggunakan capacity annealing untuk mengontrol kekuatan KL divergence selama training:

```text
total_loss = reconstruction_loss + abs(kl_divergence - capacity)
```

Dimana `capacity` meningkat dari 0 menuju `capacity_target` (0.5) selama `capacity_warmup_epochs` (60 epoch) pertama, lalu tetap pada nilai target.

Komponen ini mencegah KL divergence terlalu besar di awal training saat latent space belum terstruktur dengan baik.

## N. Preprocessing Contract

Kontrak preprocessing final: `stage2-final-v2-bounded-ip-zscore`

### Activity Mapping

Nilai `aksi` dari backend dipetakan ke 10 label training berikut:

| Backend (`aksi`) | Label Training |
|---|---|
| `LOGIN_SUCCESS` | Login |
| `LOGOUT` | Logout |
| `CREATE_BERKAS`, `UPDATE_BERKAS`, `DELETE_BERKAS`, `PERUBAHAN_STATUS_ARSIP`, `RETENSI_INAKTIF` | Input Berkas |
| `CREATE_USER`, `UPDATE_USER`, `DELETE_USER` | Kelola User |
| `CREATE_PERKARA`, `UPDATE_PERKARA`, `DELETE_PERKARA` | Lihat Perkara |
| `ACCESS_BERKAS_FILE` | Lihat Berkas |
| `CREATE_RAK`, `UPDATE_RAK`, `DELETE_RAK` | Kelola Kode Klasifikasi |
| `REQUEST_RESET_PASSWORD`, `RESET_PASSWORD` | Dashboard |
| `AJUKAN_PEMINJAMAN`, `SETUJUI_PEMINJAMAN`, `PINJAM`, `PENGEMBALIAN`, `TOLAK_PEMINJAMAN`, `UPDATE_PEMINJAMAN`, `DELETE_PEMINJAMAN` | Cari Berkas |
| `VERIFIKASI_INTEGRITAS_BERKAS`, `POTENSI_ANOMALI_HASH_BERKAS` | Verifikasi |
| `SETUP_2FA_GENERATE`, `AKTIVASI_OTP`, `DISABLE_2FA_EMAIL_CHANGED` | Dashboard |

Total label training: 10.

### Status Mapping

| Backend | Training Label |
|---|---|
| `SUCCESS`, `VALID` | Berhasil |
| `FAILED`, `GAGAL`, `ERROR` | Gagal |

### Device Normalization

User-Agent dari backend dinormalisasi ke kelas training secara case-insensitive:

| Pattern User-Agent | Training Label |
|---|---|
| mengandung `android` | Android |
| mengandung `iphone` atau `ipad` | iPhone |
| mengandung `windows nt 10.0` atau `windows nt 6.1` | Windows |
| pattern lain / tidak dikenal | Windows (fallback) |

### IP Conversion

IPv4 dikonversi menjadi unsigned 32-bit integer menggunakan `ipaddress.ip_address()`:

```python
int(ipaddress.ip_address(ipv4_string))
```

IPv6 ditolak.

### user_id dan IP Clipping (Bounded Z-Score)

Setelah StandardScaler diterapkan menggunakan parameter dari data training, hasil standardisasi untuk `ip_address` dan `user_id` dibatasi pada rentang z-score [-3, 3]:

```python
IP_ZSCORE_BOUNDS = (-3.0, 3.0)
scaled[:, IP_FEATURE_INDEX] = np.clip(scaled[:, IP_FEATURE_INDEX], *IP_ZSCORE_BOUNDS)
scaled[:, USERID_FEATURE_INDEX] = np.clip(scaled[:, USERID_FEATURE_INDEX], *IP_ZSCORE_BOUNDS)
```

Pembatasan hanya diterapkan pada `ip_address` dan `user_id`. Fitur lain (`activity`, `status`, `device`, `duration_ms`, `object_count`, `hour`, `day_of_week`) tidak di-clip.

Pada data training, nilai `user_id` dan `ip_address` sudah berada dalam rentang [-3, 3] sehingga clipping tidak mengubah data training. Clipping hanya mempengaruhi inference pada data produksi yang memiliki nilai out-of-distribution.

Tanpa clipping, `user_id` produksi yang jauh lebih besar daripada rentang training (range training: 1-86, mean 50.55) dapat menghasilkan z-score ekstrem dan mendominasi reconstruction error. Dengan bounded z-score, pengaruh nilai out-of-distribution dibatasi sehingga fitur perilaku lain tetap dapat berkontribusi terhadap anomaly score.

### Timestamp

Timestamp dikonversi ke timezone Asia/Jakarta (WIB) jika aware. Timestamp naive diasumsikan WIB.

### duration_ms

`duration_ms` dihitung dari durasi aktual operasi backend:

```javascript
const operationStart = Date.now();
// ... operasi controller ...
const duration = Date.now() - operationStart;
```

Nilai dalam milidetik, non-negatif.

### object_count

Saat ini seluruh operasi backend merupakan operasi single-object sehingga `object_count = 1`:

- satu user
- satu berkas
- satu perkara
- satu peminjaman
- satu keputusan/verifikasi

### StandardScaler dan OrdinalEncoder

Keduanya di-fit hanya menggunakan data training normal. Production request hanya menggunakan `transform` dari artifact hasil training, bukan `fit` ulang.

## O. Arsitektur Final

```text
9 → 64 → 32 → 8 → 32 → 64 → 9
```

| Komponen | Detail |
|---|---|
| Input dimension | 9 |
| Encoder | Linear(9, 64) → ReLU → Dropout(0.2) → Linear(64, 32) → ReLU |
| Latent mean | Linear(32, 8) |
| Latent logvar | Linear(32, 8) |
| Decoder | Linear(8, 32) → ReLU → Linear(32, 64) → ReLU → Linear(64, 9) |
| Output dimension | 9 |
| Output activation | linear |
| Optimizer | Adam, learning rate 0.001 |
| Epoch | 100 |
| Batch size | 30004 (training) |
| KL capacity target | 0.5 |
| KL capacity warmup | 60 epoch |
| Inference | deterministic posterior mean (mu) |
| Parameter count | 6.233 |

## P. Training Data

| Aspek | Nilai |
|---|---|
| Dataset | 15.000 data sintetis |
| Training set | 6.692 rows (1.623 sesi, 0 anomali) |
| Validation set | 4.168 rows (986 sesi, 752 anomali) |
| Test set | 4.140 rows (986 sesi, 748 anomali) |
| Split | Berbasis session_id, seed 42 |
| Session overlap | 0 antar split |
| Feature order | user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week |

## Q. Pipeline Inference

```text
Audit Log (backend)
↓
Preprocessing (activity/status mapping, device normalization, IP integer, OrdinalEncoder, StandardScaler, bounded z-score)
↓
9-dimensional Feature Matrix
↓
VAE Encoder (deterministic mean)
↓
Latent Space (8)
↓
VAE Decoder
↓
9-dimensional Reconstruction
↓
Squared Reconstruction Error (9 values)
↓
Anomaly Score (mean of 9 errors)
↓
Threshold (P95 = 1.6426611317633713)
↓
Risk Level (Normal / Perlu Ditinjau / High Risk)
```

## R. Keputusan Desain Final

Berikut ringkasan keputusan desain yang berlaku untuk implementasi final:

- Input VAE menggunakan 9 feature: `user_id`, `activity`, `status`, `device`, `ip_address`, `duration_ms`, `object_count`, `hour`, `day_of_week`.
- `user_id` merupakan fitur pertama input VAE.
- `activity` merupakan representasi aktivitas training, dipetakan dari nilai `aksi` backend.
- `ip_address` dan `user_id` menggunakan bounded z-score [-3, 3] setelah StandardScaler.
- Feature kategorikal (`activity`, `status`, `device`) menggunakan Ordinal Encoding dari training data.
- Output layer berdimensi 9 dengan activation `linear`.
- Latent dimension = 8.
- Loss function = `reconstruction_loss + abs(kl_divergence - capacity)` dengan capacity annealing.
- Threshold = P95 train-normal = 1.6426611317633713.
- Anomaly score = mean squared reconstruction error pada 9 feature.
- Feature contribution = error[i] / total error.
- 3 kategori risiko: Normal, Perlu Ditinjau, High Risk.
