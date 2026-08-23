# 167 — Deployment Wiring & Endpoint Validation (Tahap 12)

## Wiring

`app.py` ditambah **satu rute kandidat terpisah** (additive; tidak ada baris
jalur lama yang diubah):

```
POST /predict-stage11   → services.inference_stage11.predict_stage11
POST /predict           → services.inference.predict          (produksi, UTUH)
GET  /health            → tidak berubah
```

Rollback: hapus rute `/predict-stage11` (atau berhenti memanggilnya) —
`/predict` produksi tidak pernah tersentuh.

## Hasil test endpoint nyata (`audit_n_stage12.py`, 24/24 PASS — t12b_checks.csv)

| Group | Check | Hasil |
|---|---|---|
| wiring | rute /predict & /predict-stage11 terdaftar | PASS ×2 |
| candidate | valid request → PredictResponse valid | PASS |
| candidate | threshold = 3.0499422550201416 | PASS |
| candidate | anomaly_score = reconstruction_error = score | PASS |
| candidate | is_anomaly bool + status NORMAL/ANOMALY | PASS |
| candidate | public IPv4 diterima | PASS |
| negative | invalid IPv4 / IPv6 / unknown activity / device / status | HTTP 400 semua, pesan eksplisit |
| regression | /predict lama tetap bekerja, skema sama | PASS |
| regression | jalur lama masih memakai threshold produksi 3.14963 & `models/vae_model.pth` | PASS |

Eksekusi nyata tanpa database: fungsi rute FastAPI dipanggil langsung pada app
instance yang sama dengan server (httpx/TestClient tidak tersedia di venv;
pemanggilan fungsi rute = kode path identik minus transport HTTP).
