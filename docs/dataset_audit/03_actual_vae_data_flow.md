# 03 — Alur Data VAE Aktual (End-to-End, Berdasarkan Source Code)

Bukti: `preprocessing.py`, `train_vae_pytorch.py`, `services/model_loader.py`, `services/inference.py`, `utils/preprocessing.py`, `utils/preprocessing_contract.py`.

## Jalur 1 — Training (AKTIF)

```
dataset/generator/raw/audit_log_dataset.csv   (15.000 baris, synthetic, seed 42)
        │  pd.read_csv(encoding="utf-8-sig")            preprocessing.py:43
        ▼
CLEANING: tidak ada (tidak ada dropna/imputasi/filter)
        ▼
FEATURE ENGINEERING:
  timestamp → hour = dt.hour ; day_of_week = dt.dayofweek     preprocessing.py:44-46
DROP kolom: timestamp, session_id, username, role, risk_level, anomaly_type   preprocessing.py:48-50
        ▼
ENCODING:
  LabelEncoder pada activity, status, device                  preprocessing.py:52-56
  ip_address → integer via ipaddress.ip_address()             preprocessing.py:58
        ▼
FEATURE SELECTION (urutan tetap):
  [user_id, activity, status, device, ip_address,
   duration_ms, object_count, hour, day_of_week]              FEATURE_COLUMNS preprocessing.py:24-34
        ▼
SCALING: StandardScaler fit_transform (fit di SELURUH 15.000 baris)          preprocessing.py:61-62
        ▼
dataset/preprocessed/X_train.npy  (15000 × 9, float64)
+ label_encoders.pkl + scaler.pkl + preprocessing_metadata.json
```

## Jalur 2 — Model & Threshold

```
train_vae_pytorch.py
  seed: random/np/torch = 42                                   train_vae_pytorch.py:143-145
  SPLIT: TIDAK ADA train/validation/test — seluruh X_train dipakai training
         (batch_size=30.004 ≥ 15.000 → efektif full-batch per epoch)          :152
  Arsitektur: encoder 9→64→32, mu/logvar 32→8, decoder 8→32→64→9; ReLU, Dropout 0.2
  Loss: MSE + |KL − capacity| dengan KL capacity annealing (target 0,5; warmup 60 epoch)
  Epochs 100, Adam lr=0.001                                    CONFIG :25-39
        ▼
models/vae_model.pth + vae_config.json + training_history.json

threshold:
  services/inference.py::compute_training_threshold()
  = persentil-95 reconstruction error atas X_train.npy (data TRAINING itu sendiri)
  → models/deployment_config.json {"threshold": ...}           inference.py:37-46
```

## Jalur 3 — Inference / Prediksi (AKTIF)

```
POST /predict {user_id, aksi, status, device, ip_address, durasi_ms, jumlah_objek, waktu}
        ▼
utils/preprocessing_contract.process_record():
  map_canonical_activity (UPPER_SNAKE_CASE/kamus bebas → 12 kelas kanonik)
  map_canonical_status    (SUCCESS/GAGAL/dll → Berhasil/Gagal/UNKNOWN)
  parse_user_agent_device (User-Agent string → 7 kelas kanonik)
  map_ip_category         (IP → 6 kategori: localhost/private/public/UNKNOWN)
  transform_numeric_features (max(0), log1p untuk durasi_ms & jumlah_objek)
  parse_timestamp_wib     (tz-aware→Asia/Jakarta; naive DIANGGAP UTC lalu dikonversi)
        ▼
LabelEncoder dari dataset/preprocessed/label_encoders.pkl
  (_encode_canonical_value: nilai di luar kamus → "UNKNOWN" bila ada, else fallback 0)
  catatan: encoder ip_address TIDAK ADA di artefak training → ip_encoded = 0  utils/preprocessing.py:75
        ▼
scaler.transform (StandardScaler produksi) → astype(float32) → (1, 9)
        ▼
VAE (models/vae_model.pth) → reconstruction error MSE per baris      inference.py:22-34
        ▼
error > threshold (deployment_config.json) → anomali                app.py /predict
```

## Jawaban Langsung

| Pertanyaan | Jawaban berbasis bukti |
|---|---|
| Dataset input training | `dataset/generator/raw/audit_log_dataset.csv` → `X_train.npy` |
| Dataset validation | **tidak ada** — split validasi tidak dilakukan pada jalur aktif |
| Dataset testing | **tidak ada** pada jalur aktif. (`evaluate.py` lama membuat sampel uji sintetis via perturbasi, memakai model Keras legacy — bukan pipeline PyTorch aktif). Artefak Stage 5 punya split TRAIN/VAL/TEST tetapi tak pernah dipakai retrain |
| Dataset inference | payload `/predict` melalui kontrak kanonik (bukan CSV) |
| Preprocessing training | LabelEncoder + IP→integer + StandardScaler (tanpa log1p) |
| Preprocessing inference | kontrak kanonik + log1p numerik + kategori IP (berbeda dari training!) |
| Encoder | `label_encoders.pkl` (activity/status/device) |
| Scaler | `scaler.pkl` (StandardScaler, fit pada 15.000 baris synthetic) |
| Feature list | 9 fitur: user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week |
| Model | `models/vae_model.pth` (PyTorch 9-64-32-8 / 8-32-64-9) |
| Threshold | persentil-95 error training, tersimpan di `models/deployment_config.json` |

## Perbedaan Kritis Training vs Inference (TEMUAN, tidak diperbaiki)

1. **Representasi `ip_address`**: training = integer numerik dari alamat IP; inference = indeks LabelEncoder atas kategori (`_encode_canonical_value(encoders["ip_address"] …)`), dan karena `ip_address` tidak termasuk artefak encoder training, inference selalu memakai **nilai 0**.
2. **Skala numerik**: training memasukkan `duration_ms`/`object_count` mentah ke StandardScaler; inference memasukkan hasil `log1p`. Distribusi input kedua jalur berbeda meski scaler sama.
3. **Encoding jam**: training memakai jam lokal file synthetic apa adanya; inference mengonversi waktu naive sebagai UTC→WIB (menggeser jam +7).
4. Kamus `activity` training (bahasa Indonesia, mis. `Lihat Perkara`) vs produksi (`UPPER_SNAKE_CASE`) dijembatani `map_canonical_activity`; kelas kanonik seperti "Akses Berkas" tidak pernah muncul di data training.

Semua poin di atas adalah kondisi aktual implementasi saat audit; tidak diubah.
