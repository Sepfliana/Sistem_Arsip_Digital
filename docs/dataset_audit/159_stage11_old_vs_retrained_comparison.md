# 159 — Old vs Retrained Comparison (Tahap 11)

## Protokol

Baris test/validasi IDENTIK; tiap model dievaluasi dengan preprocessing
pasangannya sendiri:

- Model lama (`models/vae_model.pth`) ← matrix produksi lama
  `dataset/preprocessed/X_train.npy` (scaler full-fit) + threshold produksi
  3.14963.
- Model baru (`models/retrained/vae_model_stage11.pth`, best-val epoch 99) ←
  final scaler train-only + threshold P95-train baru 3.04994.

## Hasil (test split, label companion)

| Metrik | Model lama | Model retrained |
|---|---|---|
| TP / FN | 65 / 150 | 66 / 149 |
| FP / TN | 52 / 1964 | 52 / 1964 |
| Precision | 0.5556 | 0.5593 |
| Recall | 0.3023 | **0.3070** |
| F1 | 0.3916 | **0.3964** |
| Mean recon error test (pipeline masing-masing) | 0.9511 | 0.9379 |

Validation: F1 lama 0.3725 vs baru 0.3693 (setara).

## Verdict

**NOT DIRECTLY COMPARABLE secara loss/preprocessing — PARTIALLY COMPARABLE
pada metrik deteksi.** Skaler berbeda (full-fit vs train-only-fit) sehingga
nilai reconstruction error & loss TIDAK boleh dibandingkan langsung. Pada
metrik deteksi baris-yang-sama, performa kedua model SETARA (F1 0.392 vs
0.396; selisih ±1 anomali). Klaim "lebih baik" tidak diajukan; perbedaan dalam
margin noise. Nilai utama retraining = dataset kini terdokumentasi bersih,
split leakage-controlled, dan artefak model+threshold reproducible.
