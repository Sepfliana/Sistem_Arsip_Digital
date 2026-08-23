# Stage 11 — Model Retraining & Evaluation Report

## 1. Tujuan
Melatih ulang VAE pada FINAL dataset Stage 10 dan mengevaluasinya secara
reproducible — tanpa menyentuh model/threshold produksi.

## 2. Existing Model Audit
Arsitektur 9-64-32-8/8-32-64-9, KL-capacity annealing (0.5/60ep), Adam 1e-3,
full-batch, 100 epoch, seed 42, threshold P95-train. Dipertahankan seluruhnya;
tambahan metodologis: monitoring val-loss + best-val model selection (`146`).

## 3. Final Dataset
Train 10503×9 / Validation 2266×9 / Test 2231×9 float32 — checksum cocok
Stage 10; NaN/Inf=0 (`147`).

## 4. Model Architecture
Identik existing; parameter count **6.233**; input contract tepat 9 fitur
perilaku tanpa label/hash/path (`148`).

## 5. Training Configuration
Lihat `149` — tidak ada perubahan hyperparameter; deterministik penuh
(seed 42 py/numpy/torch + deterministic algorithms).

## 6. Training Process
100 epoch full-batch; history lengkap per epoch (`150`, kurva `151`).

## 7. Validation & pemilihan model
Best validation loss **0.948609 @ epoch 99** dipilih sebagai model final;
tidak ada tanda overfitting; underfitting ringan (val masih menurun tipis).

## 8. Threshold
P95 reconstruction error TRAIN model terpilih = **3.0499422550201416**
(metodologi existing dihitung ulang); validation P95 hanya referensi;
test tidak digunakan (`154`).

## 9. Test Evaluation (threshold tetap, tidak diubah)

| Metrik | Validation | Test |
|---|---|---|
| TP/TN/FP/FN | 65/1979/51/171 | 66/1964/52/149 |
| Precision | 0.5603 | 0.5593 |
| Recall | 0.2754 | 0.3070 |
| F1 | 0.3693 | **0.3964** |
| Accuracy | 0.9020 | 0.9099 |
| Specificity | 0.9749 | 0.9742 |
| FPR / FNR | .0251 / .7246 | .0258 / .6930 |
| Flag rate (pred anomali) | 5.12% (116) | 5.29% (118) |

Confusion matrix test: [[TN 1964, FP 52], [FN 149, TP 66]].

## 10. Anomaly Type Evaluation
Deteksi kuat: verifikasi_massal .92/.93, ip_berubah .63/.60,
peminjaman_massal .57/.50, durasi_tidak_wajar .52/.16.
Lemah: login_luar_jam ±.09, device_berubah 0–.07, aktivitas_terlalu_cepat 0
(`156`). VAE hanya menghasilkan skor rekonstruksi — bukan prediksi tipe.

## 11. Old vs Retrained Model
NOT DIRECTLY COMPARABLE untuk loss (scaler beda); metrik deteksi setara:
F1 test 0.3916 (lama) vs 0.3964 (baru) pada baris identik (`159`).
Real PostgreSQL 337 record: tidak dipakai training/threshold; status =
external behavioral reference untuk Tahap 12.

## 12. Leakage Validation
Semua check PASS — test bebas dari training & threshold; label/integrity
bebas dari input (`157`).

## 13. IP Inference Blocker
**OPEN** — sengaja tidak disentuh. Status model:
**TRAINING VALIDATED / DEPLOYMENT NOT YET VALIDATED.**

## 14. Model Artifacts
`models/retrained/`: vae_model_stage11.pth (sha256 `1e7b…` lihat metadata),
stage11_threshold.json, stage11_model_metadata.json (`158`).
Produksi utuh: vae_model.pth, deployment_config.json tidak berubah.

## 15. Limitations
Overlap distribusi error besar (test 0.71) → recall subtil rendah; threshold
P95-train membatasi flag ±5%; kategorikal ordinal encoding membatasi
sensitivitas anomali device/login-jam; single-threshold operating point.

## 16. Kesimpulan
Model **berhasil dilatih** (deterministik) dan **dievaluasi** (F1 test .3964,
accuracy .9099, specificity .9742). Threshold baru 3.04994 terdokumentasi
tanpa sentuhan test. Comparable dengan model lama hanya secara metrik deteksi —
hasil SETARA. **Deployment readiness: NOT READY** hingga parity inference
(IP/vocab/log1p/timezone) diselesaikan pada Tahap 12.
