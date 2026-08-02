# AI Service - Sistem Arsip Digital

AI Service ini mendeteksi aktivitas pengguna yang tidak normal dari tabel `audit_log` menggunakan Variational Autoencoder (VAE). Service ini hanya menganalisis audit log dan bukan deteksi malware.

## Struktur Folder

```text
ai-service/
├── app.py
├── config.py
├── preprocessing.py
├── train.py
├── evaluate.py
├── predict.py
├── requirements.txt
├── README.md
├── dataset/
│   └── dataset_vae.csv
├── model/
│   ├── vae_model.keras
│   ├── scaler.pkl
│   ├── encoders.pkl
│   └── threshold.json
├── logs/
│   ├── training.log
│   └── prediction.log
├── training/
│   ├── history.json
│   └── evaluation_metrics.json
└── utils/
    ├── database.py
    ├── encoder.py
    ├── logging_utils.py
    ├── scaler.py
    └── vae.py
```

File di `dataset/`, `model/`, `logs/`, dan `training/` dibuat atau diperbarui saat preprocessing, training, dan prediksi dijalankan.

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

## Preprocessing

```bash
python preprocessing.py
```

Perintah ini membaca tabel `audit_log`, membersihkan data, membuat fitur numerik, menyimpan encoder dan scaler, lalu membuat `dataset/dataset_vae.csv`.

## Training

```bash
python train.py
```

Training akan membuat:

- `model/vae_model.keras`
- `model/scaler.pkl`
- `model/encoders.pkl`
- `model/threshold.json`
- `logs/training.log`
- `training/history.json`

Threshold anomali dihitung dari reconstruction error dengan rumus `mean + 3 * standard deviation`.

## Menjalankan Server

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

Endpoint tersedia:

- `GET /health`
- `POST /predict`
- `POST /retrain`
- `POST /evaluate`
- `GET /model-info`

## Predict

Contoh request:

```bash
curl -X POST http://localhost:8000/predict ^
  -H "Content-Type: application/json" ^
  -d "{\"timestamp\":\"2026-06-29T10:00:00\",\"user_id\":1,\"role\":\"admin\",\"action\":\"LOGIN\",\"module\":\"AUTH\",\"ip_address\":\"127.0.0.1\",\"device\":\"desktop\",\"status\":\"SUCCESS\",\"duration_ms\":120,\"object_count\":1}"
```

Contoh output:

```json
{
  "score": 0.0123,
  "threshold": 0.0456,
  "status": "NORMAL"
}
```

## Retrain

```bash
curl -X POST http://localhost:8000/retrain
```

Endpoint ini menjalankan ulang preprocessing, training model VAE, dan perhitungan threshold berdasarkan data terbaru di `audit_log`.

## Evaluasi

```bash
curl -X POST http://localhost:8000/evaluate
```

Endpoint ini menghasilkan data pengujian VAE untuk BAB IV, meliputi confusion matrix, precision, recall, F1-score, ROC, dan AUC. Hasil evaluasi disimpan ke `training/evaluation_metrics.json`.

## Status AI Development

| Sprint | Status | Fokus |
|---|---|---|
| Sprint 1 | Selesai | Fondasi preprocessing audit log, utilitas database, encoder, scaler, dan logging. |
| Sprint 2 | Selesai | Blueprint arsitektur VAE dan spesifikasi hyperparameter. |
| Sprint 3 | Selesai | Implementasi model VAE, training, reconstruction error, dan threshold. |
| Sprint 4 | Selesai | Prediction pipeline dan evaluasi deteksi anomali. |
| Sprint 5 | Selesai | Integrasi API, monitoring dasar, dokumentasi eksperimen, dan endpoint evaluasi. |
