# VAE Architecture Blueprint - Sistem Arsip Digital

Dokumen ini adalah blueprint arsitektur Variational Autoencoder (VAE) untuk deteksi anomali audit log pada Sistem Arsip Digital. Sprint 2 hanya mendefinisikan desain model dan belum melakukan implementasi model, training, threshold, atau artefak Keras.

## A. Tujuan Model

Model VAE dirancang untuk mempelajari pola aktivitas normal dari tabel `audit_log`, lalu mendeteksi aktivitas yang tidak normal berdasarkan reconstruction error.

Model ini hanya digunakan untuk anomaly detection pada audit log. Model tidak digunakan untuk prediksi kategori dokumen, identifikasi pengguna, autentikasi, atau malware detection.

## B. Input Model

Input model berasal dari hasil preprocessing terbaru pada `ai-service/preprocessing.py`.

Feature yang digunakan:

| No | Feature | Sumber | Transformasi |
|---:|---|---|---|
| 1 | `role` | `audit_log.role` | Label Encoding |
| 2 | `action` | `audit_log.action` | Label Encoding |
| 3 | `module` | `audit_log.module` | Label Encoding |
| 4 | `status` | `audit_log.status` | Label Encoding |
| 5 | `device` | `audit_log.device` | Label Encoding |
| 6 | `ip_address` | `audit_log.ip_address` | Hash/integer representation, lalu StandardScaler |
| 7 | `duration_ms` | `audit_log.duration_ms` | StandardScaler |
| 8 | `object_count` | `audit_log.object_count` | StandardScaler |
| 9 | `hour` | `audit_log.timestamp` | Ekstraksi jam dari timestamp |
| 10 | `day_of_week` | `audit_log.timestamp` | Ekstraksi hari dalam minggu dari timestamp |

`user_id` tetap diambil dari database dan dapat muncul pada payload, tetapi tidak menjadi input VAE karena merupakan identifier dan berisiko membuat model menghafal identitas pengguna, bukan pola aktivitas.

## C. Jumlah Input Feature

Jumlah input feature mengikuti `FEATURE_COLUMNS` pada `ai-service/preprocessing.py`.

```text
FEATURE_COLUMNS = 10
```

Dengan demikian, input layer pada Sprint 3 harus memiliki dimensi input sebesar `10`.

## D. Arsitektur Encoder

Encoder bertugas memetakan feature vector audit log ke latent space.

Blueprint arsitektur:

```text
Input (10)
↓
Dense(64)
↓
BatchNormalization
↓
ReLU
↓
Dropout(0.2)
↓
Dense(32)
↓
BatchNormalization
↓
ReLU
↓
Latent Mean (8)

Latent Log Variance (8)
```

Encoder tidak menghasilkan kelas atau label. Encoder hanya menghasilkan representasi laten dari pola audit log.

Batch Normalization digunakan untuk membuat proses training lebih stabil dan mempercepat konvergensi. Dropout(0.2) digunakan untuk mengurangi overfitting, terutama karena audit log dapat memiliki pola aktivitas yang berulang.

## E. Arsitektur Decoder

Decoder bertugas merekonstruksi kembali feature vector dari latent space.

Blueprint arsitektur:

```text
Latent Space (8)
↓
Dense(32)
↓
BatchNormalization
↓
ReLU
↓
Dropout(0.2)
↓
Dense(64)
↓
BatchNormalization
↓
ReLU
↓
Output (10)
```

Decoder harus menghasilkan output dengan jumlah dimensi yang sama dengan input, yaitu `10`.

## F. Output Layer

Output layer merekonstruksi feature audit log yang sudah diproses.

```text
Output dimension = 10
Activation = linear
```

Activation `linear` dipilih karena input akhir berupa nilai numerik hasil encoding dan scaling. Model harus bebas merekonstruksi nilai kontinu, bukan memetakan ke probabilitas kelas.

## G. Reconstruction Error

Reconstruction error mengukur selisih antara input asli dan hasil rekonstruksi decoder.

Desain metrik:

```text
reconstruction_error = mean(square(input_vector - reconstructed_vector))
```

Aktivitas normal diharapkan memiliki reconstruction error rendah karena mirip dengan pola training. Aktivitas tidak normal diharapkan menghasilkan reconstruction error lebih tinggi.

Semakin kecil reconstruction error berarti aktivitas semakin mirip dengan pola normal yang dipelajari VAE. Semakin besar reconstruction error berarti aktivitas semakin jauh dari distribusi normal sehingga memiliki probabilitas lebih tinggi untuk dikategorikan sebagai anomali.

## H. Threshold

Threshold belum dihitung pada Sprint 2.

Threshold baru dihitung pada Sprint 3 setelah model dilatih menggunakan data training. Rekomendasi awal:

```text
threshold = mean(reconstruction_error_training) + 3 * std(reconstruction_error_training)
```

Nilai threshold akan disimpan sebagai artefak pada sprint training, bukan pada sprint blueprint.

## Rekomendasi Hyperparameter

| Hyperparameter | Rekomendasi | Alasan |
|---|---:|---|
| Latent Dimension | `8` | Cukup kecil untuk memaksa kompresi pola audit log, tetapi masih mampu merepresentasikan variasi aktivitas seperti role, module, action, waktu, durasi, dan jumlah objek. |
| Hidden Layers | `[64, 32]` encoder dan `[32, 64]` decoder | Ukuran ini ringan untuk tabular audit log dan menjaga model tidak terlalu besar untuk dataset tugas akhir. |
| Activation Function | `relu` | Cocok untuk dense layer tabular dan membantu menangkap pola non-linear pada aktivitas audit log. |
| Output Activation | `linear` | Output merekonstruksi feature numerik, bukan probabilitas kelas. |
| Optimizer | `adam` | Stabil untuk training neural network tabular dan umum dipakai sebagai baseline kuat. |
| Loss Function | `reconstruction_loss + kl_divergence` | Sesuai tujuan VAE: rekonstruksi input sambil menjaga latent space teratur. |
| Reconstruction Loss | `mean_squared_error` | Cocok karena seluruh feature akhir numeric setelah preprocessing. |
| Epoch | `100` | Batas atas training yang cukup untuk eksperimen awal, dikombinasikan dengan early stopping pada Sprint 3. |
| Batch Size | `32` | Ukuran batch umum untuk dataset tabular skala kecil-menengah. |
| Validation Split | `0.2` | Memberi evaluasi generalisasi tanpa memerlukan dataset terpisah pada tahap awal penelitian. |
| Learning Rate | `0.001` | Learning rate 0.001 dipilih karena merupakan nilai default optimizer Adam yang telah banyak digunakan sebagai baseline stabil untuk training neural network pada data tabular. |
| Random Seed | `42` | Membuat eksperimen lebih mudah direproduksi. |

## Desain Loss Function

Loss function VAE terdiri dari dua komponen.

### Reconstruction Loss

Reconstruction loss menghitung seberapa baik decoder membangun ulang input audit log.

```text
reconstruction_loss = mean_squared_error(input_vector, reconstructed_vector)
```

Jika aktivitas audit log mirip dengan pola normal yang dipelajari, nilai reconstruction loss seharusnya rendah.

### KL Divergence

KL Divergence menjaga distribusi latent space agar mendekati distribusi normal standar.

```text
kl_divergence = -0.5 * sum(1 + log_variance - mean^2 - exp(log_variance))
```

Komponen ini membantu latent space tetap teratur dan mengurangi kecenderungan model hanya menghafal data.

### Total Loss

```text
total_loss = reconstruction_loss + kl_divergence
```

Sprint 2 hanya mendokumentasikan desain loss. Implementasi loss dilakukan pada Sprint 3.

## Desain Pipeline

```text
Audit Log
↓
Preprocessing
↓
Feature Vector
↓
Encoder
↓
Latent Space
↓
Decoder
↓
Reconstruction
↓
Reconstruction Error
↓
Threshold
↓
Normal / Anomaly
```

## Keputusan Desain Untuk Sprint 3

- Input VAE menggunakan 10 feature dari `FEATURE_COLUMNS`.
- `user_id` tidak menjadi feature model.
- Feature kategorikal memakai Label Encoding dari Sprint 1.
- `ip_address`, `duration_ms`, dan `object_count` memakai StandardScaler.
- Output layer harus berdimensi 10 dengan activation `linear`.
- Latent dimension menggunakan nilai awal `8`.
- Loss function menggunakan reconstruction loss ditambah KL Divergence.
- Threshold tidak dibuat manual pada Sprint 2 dan baru dihitung setelah training pada Sprint 3.
