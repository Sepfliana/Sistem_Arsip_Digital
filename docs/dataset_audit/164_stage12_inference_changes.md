# 164 — Perubahan Preprocessing Inference & Resolusi IP Parity (Tahap 12)

## File baru (satu-satunya perubahan source aplikasi)

`ai-service/services/inference_stage11.py` — modul kandidat, tidak mengubah
`app.py`, `services/inference.py`, `model_loader.py`, atau contract lama.

## IP PARITY — RESOLVED

- Training-side: `int(ipaddress.ip_address(v))` → inference baru memakai fungsi
  yang sama (`_encode_ip`) sehingga IPv4 valid menghasilkan nilai identik
  (test: "192.168.1.77" → 3232235853 = training encoding).
- **IPv6/invalid: TIDAK dipalsukan** → `ValueError` eksplisit dengan pesan jelas
  ("Hanya IPv4 yang didukung kontrak training"), konsisten dikonsumsi endpoint
  sebagai HTTP 400.
- Fallback `ip_encoded=0` dari jalur lama TIDAK dipertahankan di jalur baru.

## Peta artefak encoder/scaler/model

| Kebutuhan | Artefak sumber | Sifat |
|---|---|---|
| activity/status/device codes | `dataset/encoded/stage9_label_encoders.pkl` | LabelEncoder ASLI Tahap 9 — bukan encoder baru; unknown → ValueError (tidak ada mapping salah diam-diam) |
| Scaling | `dataset/final/scaler/final_train_scaler.pkl` | fit TRAIN-only 10.503 baris (n_samples_seen_ terverifikasi) |
| Model | `models/retrained/vae_model_stage11.pth` | best-val epoch 99 |
| Threshold | `models/retrained/stage11_threshold.json` | 3.0499422550201416 (tidak diubah) |

## Numeric parity

user_id int passthrough · duration_ms/object_count mentah (tanpa log1p) ·
timestamp naive lokal → dt.hour / dt.dayofweek (Monday=0); tz-aware dikonversi
ke WIB lalu naive (didokumentasikan); tanpa cyclical encoding.

## Unknown policy

Closed vocabulary: nilai di luar vocab training ditolak dengan error eksplisit
(daftar kelas valid disertakan) — lebih dapat dipertanggungjawabkan daripada
fallback diam-diam ke UNKNOWN/0.
