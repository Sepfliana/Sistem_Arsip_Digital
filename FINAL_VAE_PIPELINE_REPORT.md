# Final VAE Pipeline Report

## Status akhir

**FINAL VAE PIPELINE — PASS**

Satu jalur aktif adalah:

`audit log HTTP -> request IPv4 context -> backend /predict -> FastAPI -> Stage 2 v2 preprocessing -> VAE final -> nine feature errors -> mean anomaly score -> P95 train-normal threshold -> risk/explanation`.

## Dataset dan kontrak final

- SSOT: `ai-service/dataset/final_stage1_ssot/`.
- Split sesi: train `6.692` baris / `1.623` sesi / `0` anomali; validation `4.168` / `986`; test `4.140` / `986`; tidak ada overlap sesi.
- Urutan input tetap: `user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week`.
- Kontrak preprocessing: `stage2-final-v2-bounded-ip-zscore`. Encoder kategorikal dan `StandardScaler` dipasangkan dari train normal saja.
- IPv4 tetap integer unsigned 32-bit. Audit integrasi menemukan train hanya mencakup `192.168.1.*`; agar IPv4 valid di luar rentang itu tidak menghasilkan jutaan standard deviation, z-score IP sesudah transform dibatasi `(-3.0, 3.0)` secara identik pada seluruh jalur. Ini tidak menggunakan label, bobot feature, perubahan jumlah feature, atau threshold.

## Model, skor, dan threshold

- Arsitektur terkunci: `9 -> 64 -> 32 -> latent 8 -> 32 -> 64 -> 9`; ReLU, dropout 0,2, Adam 0,001, 100 epoch, capacity 0,5/warm-up 60.
- Fit hanya memakai train normal. Validation hanya dipantau; test tidak dipakai untuk fitting atau threshold.
- Error setiap feature adalah squared reconstruction error. `anomaly_score = mean(9 feature errors)` tanpa weighting.
- Contribution = `feature_error / sum(feature_errors)`; total nol ditangani aman.
- Threshold final: **1.642661131763**, P95 reconstruction score train normal. Referensi `mean + 3σ` direkam tetapi tidak dipilih, karena keputusan forensik Tahap 11 menetapkan P95 train sebagai ground truth.

## Evaluasi jujur

| Split | Accuracy | Precision | Recall | F1 | TN | FP | FN | TP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Validation | 0.8673 | 0.6743 | 0.5120 | 0.5820 | 3230 | 186 | 367 | 385 |
| Test | 0.8630 | 0.6625 | 0.4933 | 0.5655 | 3204 | 188 | 379 | 369 |

- Distribusi test: mean score `4.011335`, median `0.903952`, P95 `3.876782`.
- Kontribusi IP rata-rata seluruh test `3.56%`; bukan lagi dominan akibat input tak-terbatas. Untuk label `ip_berubah`, IP boleh dominan secara semantik karena memang feature itulah yang diubah.
- Hour tetap memberi sinyal tanpa aturan buatan: error hour rata-rata jam kerja `0.613028` dan luar jam kerja `3.897394`.
- SSOT tidak memiliki baris loopback. Uji converter/inference tetap dilakukan langsung: `{"loopback": {"integer": 2130706433, "z_score": -3.0, "in_bounds": true}, "private": {"integer": 167772161, "z_score": -3.0, "in_bounds": true}, "public": {"integer": 134744072, "z_score": -3.0, "in_bounds": true}}`. Hasil ini membuktikan input finite dan bounded; ia bukan klaim metrik klasifikasi localhost yang tidak tersedia dalam SSOT.

## FastAPI dan backend

- FastAPI hanya mengekspos `/predict` sebagai inference production; `/predict-stage11` tidak diregistrasikan.
- `backend/services/auditLogService.js` menormalkan setiap URL konfigurasi ke `/predict`, lalu memanggilnya dengan payload berkontrak final.
- Middleware `backend/utils/auditRequestContext.js` meneruskan IPv4 request dan User-Agent ke semua call-site audit. Jika IPv4 valid tidak ada, log tetap disimpan dan inferensi sengaja dilewati—alamat `unknown` tidak dipalsukan menjadi input VAE.

## Artifact final

- `ai-service/models/final_vae/vae_model_final.pth`
- `model_config.json`, `model_metadata.json`, `training_history.json`, `training_metadata.json`, `threshold.json`, `evaluation.json`, `final_validation_results.json`
- `ai-service/dataset/final_stage1_ssot/preprocessing_stage2/` berisi encoder, scaler, feature contract, matrix per split, manifest, dan hasil parity.

## Status pipeline lama

| Jalur/artifact | Status | Keterangan |
|---|---|---|
| `services/final_vae_pipeline.py` + `models/final_vae/` | FINAL / ACTIVE | Satu-satunya jalur `/predict`. |
| `dataset/final_stage1_ssot/preprocessing_stage2/` | FINAL / ACTIVE | Kontrak v2 paired dengan model final. |
| `preprocessing_stage2_v1_unbounded_legacy/` + `final_vae_v1_unbounded_ip_candidate/` | CANDIDATE / PRESERVED | Dipertahankan sebagai bukti sebelum koreksi distorsi IP; tidak dimuat. |
| `services/inference_stage11.py` + `models/retrained/` | CANDIDATE / DISCONNECTED | Route eksperimen tidak lagi terdaftar. |
| `models/vae_model.pth`, `dataset/preprocessed/`, `utils/preprocessing.py` | LEGACY | Tidak dipanggil jalur final. |
| `model/*.keras`, `train.py`, `evaluate.py` | LEGACY / DEAD | Pipeline Keras lama. |
| `stage7/`, `models/candidate/`, dataset retraining candidate | EXPERIMENTAL / CANDIDATE | Bukan production. |
| `*_legacy_*`, `*_pre_*` | LEGACY / PRESERVED | Salinan sebelum pengalihan untuk audit/rollback. |

## Audit A–V

| Item | Pemeriksaan | Status | Bukti |
|---|---|---|---|
| A | Dataset | PASS | Stage 1 PASS; sizes 6692/4168/4140 |
| B | Split | PASS | deterministic session-based SSOT split |
| C | Leakage | PASS | session overlap=[0, 0, 0]; train anomalies=0 |
| D | Feature order | PASS | user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week |
| E | Encoder | PASS | single train-fitted categorical encoder; v2 parity PASS |
| F | Scaler | PASS | scaler fit train-only; inference transform parity |
| G | IP conversion | PASS | IPv4 32-bit + bounded z-score [-3,3] |
| H | Timestamp/timezone | PASS | naive WIB 14/19/midnight exact |
| I | Model architecture | PASS | 9→64→32→8→32→64→9, ReLU/dropout 0.2 |
| J | Training configuration | PASS | Adam 0.001, 100 epochs, capacity 0.5 at epoch 60; train-normal only |
| K | Reconstruction/KL loss | PASS | MSE reconstruction + KL capacity loss |
| L | Reconstruction error | PASS | nine squared reconstruction errors per record |
| M | Anomaly score | PASS | score exactly mean of nine errors; no weights |
| N | Feature contribution | PASS | contribution normalized safely; dominant features returned |
| O | Threshold | PASS | P95 train-normal=1.642661131763; test unused |
| P | Test metrics | PASS | test confusion totals=4140; F1=0.565517 |
| Q | FastAPI | PASS | single FastAPI /predict uses paired v2 artifacts |
| R | Backend | PASS | backend pinned to /predict with request IPv4 context |
| S | Artifact consistency | PASS | model, threshold, history, encoder, scaler, contract hashes match |
| T | Determinism | PASS | deterministic posterior-mean inference; preprocessing diff=0 |
| U | Thesis/forensic parity | PASS | forensic P95/architecture retained; test IP contribution=3.56% |
| V | Legacy/production status | PASS | 46 preexisting artifacts checksum-preserved; v1 candidate preserved |

## File kode yang diubah

- `ai-service/utils/final_preprocessing_contract.py`
- `ai-service/finalize_preprocessing_stage2.py`
- `ai-service/validate_preprocessing_stage2.py`
- `ai-service/services/final_vae_pipeline.py`
- `ai-service/train_vae_pytorch.py`
- `ai-service/services/inference.py`, `services/model_loader.py`, `app.py`, `schemas/predict_response.py`
- `backend/utils/auditRequestContext.js`, `backend/app.js`, `backend/services/auditLogService.js`
- `ai-service/requirements.txt`
