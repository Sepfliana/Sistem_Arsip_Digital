# 160 — Tabel Skripsi: Proses Retraining & Evaluasi Model (Tahap 11)

| Proses | Input | Metode | Output | Evaluasi |
|---|---|---|---|---|
| Training | X_train_final (10503×9) | VAE 9-64-32-8/8-32-64-9, MSE+KL-annealing, Adam lr 1e-3, full-batch, seed 42, 100 epoch | vae_model_stage11.pth (best-val state) | train loss 0.9609; val loss best 0.9486 @epoch 99 |
| Validation monitoring | X_validation (2266×9) | Forward-pass per epoch (no grad) | riwayat val-loss; model selection best-val | 150_stage11_training_history.csv |
| Threshold selection | Train reconstruction errors (model terpilih) | P95 metodologi existing dihitung ulang | stage11_threshold.json = 3.04994 | validation P95 direkam sebagai referensi; test tidak dipakai |
| Testing | X_test (2231×9) | Reconstruction error → skor anomali | error per baris test | 153; distribusi normal vs anomali |
| Evaluation | X_test + label companion (evaluasi saja) | Threshold binarisasi → confusion matrix | TP/TN/FP/FN + metrik | Precision .5593 · Recall .3070 · F1 .3964 · Accuracy .9099 |
| Per-type evaluation | anomaly_type companion | Deteksi per kategori | detection rate per jenis | verifikasi_massal .9167; ip_berubah .625; peminjaman_massal .5652; login_luar_jam .0909 |
| Comparison | Baris test identik, preprocessing masing-masing pipeline | Old vs retrained | metrik deteksi berdampingan | F1 0.3916 vs 0.3964 — setara; NOT DIRECTLY COMPARABLE utk loss |

Status model: **TRAINING VALIDATED / DEPLOYMENT NOT YET VALIDATED** —
IP inference parity blocker tetap terbuka untuk Tahap 12.
