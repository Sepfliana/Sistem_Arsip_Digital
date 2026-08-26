# AI Service — Sistem Arsip Digital

AI Service mendeteksi aktivitas pengguna yang tidak normal dari tabel `audit_log` menggunakan Variational Autoencoder (VAE). Service ini hanya menganalisis audit log dan bukan deteksi malware.

## Technology

- Python 3.11+
- PyTorch
- FastAPI + uvicorn
- StandardScaler dan OrdinalEncoder (scikit-learn)
- Model artifact: `models/final_vae/`

## Struktur Folder

```text
ai-service/
├── app.py                          # FastAPI production entry point
├── config.py                       # Konfigurasi environment
├── requirements.txt                # Dependencies Python
├── train_vae_pytorch.py            # Script training final
├── finalize_preprocessing_stage2.py
├── validate_preprocessing_stage2.py
├── schemas/
│   ├── predict_request.py          # Request contract
│   └── predict_response.py         # Response contract
├── services/
│   ├── final_vae_pipeline.py       # Pipeline inference final (VAE, scoring, explanation)
│   ├── inference.py                # Compat shim ke final_vae_pipeline
│   └── model_loader.py             # Model artifact loader
├── utils/
│   ├── final_preprocessing_contract.py  # Preprocessing production
│   └── database.py
├── models/
│   └── final_vae/
│       ├── vae_model_final.pth     # Model weights PyTorch
│       ├── model_config.json       # Konfigurasi arsitektur
│       ├── model_metadata.json     # Metadata training & artifacts
│       ├── threshold.json          # Threshold P95
│       └── ...
└── dataset/
    └── final_stage1_ssot/
        ├── preprocessing_stage2/   # Encoder, scaler, feature contract
        │   ├── categorical_encoder.pkl
        │   ├── train_only_scaler.pkl
        │   └── feature_contract.json
        └── ...
```

## Install

```bash
cd ai-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Isi konfigurasi database di `ai-service/.env`:

```env
HOST=localhost
PORT=5432
DATABASE=sistem_arsip_digital
USER=postgres
PASSWORD=isi_password_database
```

## Menjalankan Server

```bash
cd ai-service
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Endpoint

| Method | Path | Keterangan |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/predict` | Inference anomaly detection |

### POST /predict

Contoh request:

```json
{
  "waktu": "2026-08-25T10:00:00",
  "user_id": 1,
  "aksi": "LOGIN_SUCCESS",
  "status": "SUCCESS",
  "device": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
  "ip_address": "192.168.1.10",
  "durasi_ms": 120,
  "jumlah_objek": 1
}
```

| Field | Tipe | Keterangan |
|---|---|---|
| `waktu` | string | Timestamp audit log (ISO format) |
| `user_id` | integer | ID user |
| `aksi` | string | Aktivitas yang dilakukan |
| `status` | string | Status hasil aktivitas |
| `device` | string | User-Agent string perangkat |
| `ip_address` | string | Alamat IP (IPv4) |
| `durasi_ms` | float | Durasi operasi dalam milidetik (default: 0.0) |
| `jumlah_objek` | float | Jumlah objek yang diproses (default: 1.0) |

Contoh response:

```json
{
  "anomaly_score": 0.845632,
  "reconstruction_error": 0.845632,
  "score": 0.845632,
  "threshold": 1.6426611317633713,
  "risk_level": "LOW",
  "timestamp": "2026-08-25T10:00:00",
  "is_anomaly": false,
  "status": "NORMAL",
  "feature_errors": {
    "user_id": 0.012,
    "activity": 0.234,
    "status": 0.001,
    "device": 0.045,
    "ip_address": 0.156,
    "duration_ms": 0.312,
    "object_count": 0.003,
    "hour": 0.078,
    "day_of_week": 0.004
  },
  "feature_contributions": {
    "user_id": 0.014,
    "activity": 0.277,
    "status": 0.001,
    "device": 0.053,
    "ip_address": 0.185,
    "duration_ms": 0.369,
    "object_count": 0.004,
    "hour": 0.092,
    "day_of_week": 0.005
  },
  "dominant_features": [
    {"feature": "duration_ms", "error": 0.312, "contribution": 0.369},
    {"feature": "activity", "error": 0.234, "contribution": 0.277},
    {"feature": "ip_address", "error": 0.156, "contribution": 0.185}
  ],
  "explanation": "Skor 0.845632 tidak melewati threshold P95 train-normal 1.642661. Kontributor dominan: duration_ms (36.9%), activity (27.7%), ip_address (18.5%).",
  "preprocessing_contract": "stage2-final-v2-bounded-ip-zscore"
}
```

## Arsitektur Model

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
| KL capacity target | 0.5 |
| KL capacity warmup | 60 epoch |
| Inference | deterministic posterior mean (mu) |
| Parameter count | 6.233 |

## Features

9 fitur dalam urutan tetap:

| No | Feature | Sumber | Transformasi |
|---:|---|---|---|
| 1 | `user_id` | `audit_log.user_id` | Ordinal Encoding, StandardScaler, bounded z-score [-3, 3] |
| 2 | `activity` | `audit_log.aksi` | Activity mapping, Ordinal Encoding |
| 3 | `status` | `audit_log.status` | Status mapping, Ordinal Encoding |
| 4 | `device` | `audit_log.device` | Device normalization, Ordinal Encoding |
| 5 | `ip_address` | `audit_log.ip_address` | IPv4 → unsigned 32-bit integer, StandardScaler, bounded z-score [-3, 3] |
| 6 | `duration_ms` | `audit_log.durasi_ms` | Durasi aktual operasi (ms), StandardScaler |
| 7 | `object_count` | `audit_log.jumlah_objek` | Jumlah objek, StandardScaler |
| 8 | `hour` | `audit_log.waktu` | Jam (0-23) dari timestamp WIB |
| 9 | `day_of_week` | `audit_log.waktu` | Hari (0=Monday, 6=Sunday) dari timestamp WIB |

## Preprocessing

Alur preprocessing production:

```text
Backend audit log
↓
Activity mapping (37 backend values → 10 training labels)
↓
Status mapping (6 backend statuses → 2 training labels)
↓
Device normalization (User-Agent → 5 training device classes)
↓
IPv4 → unsigned 32-bit integer
↓
OrdinalEncoder (fit pada training data)
↓
StandardScaler (fit pada training data)
↓
Bounded z-score [-3, 3] pada ip_address dan user_id
↓
9-dimensional feature matrix
↓
VAE inference
```

StandardScaler dan OrdinalEncoder menggunakan artifact hasil training dan tidak di-fit ulang pada production request.

### Activity Mapping

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

### Status Mapping

| Backend | Training Label |
|---|---|
| `SUCCESS`, `VALID` | Berhasil |
| `FAILED`, `GAGAL`, `ERROR` | Gagal |

### Device Normalization

| Pattern User-Agent (case-insensitive) | Training Label |
|---|---|
| mengandung `android` | Android |
| mengandung `iphone` atau `ipad` | iPhone |
| mengandung `windows nt 10.0` atau `windows nt 6.1` | Windows |
| pattern lain / tidak dikenal | Windows (fallback) |

### IP + user_id Clipping

```python
IP_ZSCORE_BOUNDS = (-3.0, 3.0)
```

Clipping diterapkan setelah StandardScaler, hanya pada `ip_address` dan `user_id`. Fitur lain tidak di-clip.

## Anomaly Score

```text
anomaly_score = mean((input - reconstruction)²)
```

Dihitung pada 9 feature errors.

## Threshold

```text
threshold = 1.6426611317633713
```

P95 reconstruction score dari data training normal.

## Risk Categories

| Kategori | Kondisi | AI Service Level |
|---|---|---|
| Normal | score ≤ threshold | LOW |
| Perlu Ditinjau | threshold < score < 1.5 × threshold | MEDIUM |
| High Risk | score ≥ 1.5 × threshold | HIGH |

Batas atas Perlu Ditinjau ≈ 2.463991697645057.

Backend menerjemahkan ke database: `HIGH` → `TINGGI`, `MEDIUM` → `SEDANG`.

## Feature Contribution

```text
contribution[i] = error[i] / sum(errors)
```

Total contribution = 1.0.

Sistem menghasilkan:
- `feature_errors`: 9 nilai error per feature
- `feature_contributions`: 9 nilai kontribusi per feature
- `dominant_features`: 3 feature dengan kontribusi terbesar
- `explanation`: teks penjelasan dalam Bahasa Indonesia

## Training

Script training final: `train_vae_pytorch.py`

| Aspek | Nilai |
|---|---|
| Dataset | 15.000 data sintetis |
| Training set | 6.692 rows (hanya data normal) |
| Validation set | 4.168 rows |
| Test set | 4.140 rows |
| Split | Berbasis session_id, seed 42 |
| Session overlap | 0 antar split |
| StandardScaler | Fit hanya training normal |
| OrdinalEncoder | Fit hanya training normal |

## Model Artifact

Artifact final tersimpan di `models/final_vae/`:

- `vae_model_final.pth` — Model weights PyTorch
- `model_config.json` — Konfigurasi arsitektur
- `model_metadata.json` — Metadata training & artifacts
- `threshold.json` — Threshold P95

Preprocessing artifacts di `dataset/final_stage1_ssot/preprocessing_stage2/`:

- `categorical_encoder.pkl` — OrdinalEncoder hasil training
- `train_only_scaler.pkl` — StandardScaler hasil training
- `feature_contract.json` — Kontrak preprocessing v2

## File Legacy

Berikut file yang bukan bagian dari pipeline production:

- `final_preprocessing_contract_v1_unbounded_legacy.py` — Preprocessing v1 sebelum bounded z-score (preserved untuk audit)
- `services/inference_stage11.py` — Pipeline eksperimen lama (tidak diregistrasikan)
- `models/retrained/`, `models/candidate/` — Model kandidat (tidak dimuat)
- `model/*.keras`, `train.py`, `evaluate.py` — Pipeline Keras lama (tidak digunakan)

## Status Development

| Sprint | Status | Fokus |
|---|---|---|
| Sprint 1 | Selesai | Fondasi preprocessing audit log, utilitas database, encoder, scaler, dan logging. |
| Sprint 2 | Selesai | Blueprint arsitektur VAE dan spesifikasi hyperparameter. |
| Sprint 3 | Selesai | Implementasi model VAE PyTorch, training, reconstruction error, dan threshold P95. |
| Sprint 4 | Selesai | Prediction pipeline, bounded z-score, feature contribution, dan explanation. |
| Sprint 5 | Selesai | Integrasi API, backend audit log context, dan validasi pipeline final. |
