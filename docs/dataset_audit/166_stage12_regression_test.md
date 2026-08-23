# 166 — Regression Test (Tahap 12)

Dijalankan tanpa database produksi (inference path tidak menyentuh DB).

| Aspek | Hasil |
|---|---|
| `services.inference` (jalur lama) importable | PASS |
| `app.py` (FastAPI) importable tanpa side-effect DB | PASS |
| Endpoint logic lama `predict(PredictRequest)` | PASS — menghasilkan skor & is_anomaly bool; response lolos skema `PredictResponse` |
| Response format baru `predict_stage11` | PASS — kunci identik: anomaly_score, reconstruction_error, score, threshold, risk_level, timestamp, is_anomaly, status |
| Error handling | ValueError dari kontrak baru dipetakan rapi (endpoint lama sudah membungkus ValueError → HTTP 400; modul baru mengikuti pola yang sama bila didaftarkan sebagai route) |
| Logging/anomaly scoring | Tidak berubah — jalur lama utuh |

Catatan integrasi opsional Tahap lanjutan: mengekspos jalur kandidat sebagai
route terpisah (mis. `/predict-stage11`) atau feature flag — sengaja TIDAK
dilakukan di Tahap 12 agar endpoint produksi tetap 100% bebas risiko; modul
kandidat siap dipasang dengan satu baris wiring saat keputusan cutover diambil.
