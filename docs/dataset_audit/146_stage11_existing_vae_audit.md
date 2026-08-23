# 146 — Audit Model VAE Existing (Tahap 11)

Sumber: `ai-service/train_vae_pytorch.py`, `services/inference.py`,
`models/vae_config.json`, `models/deployment_config.json`.

| Aspek | Nilai existing |
|---|---|
| Arsitektur | 9→64→32 encoder; mu/logvar→8; decoder 8→32→64→9 |
| Latent dimension | 8 |
| Activation | ReLU (dropout 0.2 di encoder) |
| Reconstruction loss | MSE (mean per elemen) |
| KL loss | -0.5·mean(Σ(1+logvar−μ²−e^logvar)) |
| Loss total | recon + 1.0·\|KL − capacity(epoch)\| — KL capacity annealing, target 0.5, warmup 60 epoch |
| Optimizer | Adam, lr 0.001 |
| Batch size | 30004 (= full-batch utk 15.000 baris) |
| Epoch | 100 |
| Early stopping / model selection | TIDAK ADA (fixed epochs) |
| Random seed | python/numpy/torch = 42 |
| Checkpoint | checkpoint.pth atomik + resume penuh (RNG state disimpan) |
| Threshold | P95 reconstruction error TRAIN (`inference.py:43`) → deployment_config.json = 3.14963 |
| Preprocessing dependency | dataset/preprocessed/X_train.npy + scaler.pkl + label_encoders.pkl |
| Inference dependency | utils/preprocessing_contract.py → scaler/encoder produksi |

## Keputusan Tahap 11

1. DIPERTAHANKAN: arsitektur, loss & annealing, optimizer/lr/batch/epochs, seed 42,
   metode threshold P95-train.
2. RETRAIN: bobot model — pada final dataset (train-only scaler).
3. EVALUASI ULANG: threshold (dihitung ulang dgn model baru), metrik deteksi;
   TAMBAHAN metodologis baru (terdokumentasi): monitoring validation loss per
   epoch + model selection best-val (pipeline existing tidak punya early stopping).
