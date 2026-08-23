# 151 — Training Curve (Tahap 11)

Data lengkap: `150_stage11_training_history.csv` (100 epoch).

## Bentuk kurva

- KL capacity annealing linear sampai 0.5 pada epoch 60 → train_loss naik
  terkendali selama warmup lalu menurun.
- Train loss akhir 0.960861; validation loss terbaik 0.948609 (epoch 99).
- Val loss masih menurun perlahan di akhir 100 epoch → model belum plateau
  sempurna (indikasi *underfitting ringan* / budget epoch existing yang
  dipertahankan; bukan overfitting — val loss < train loss konsisten dengan
  dropout aktif saat training + annealing KL).
- Gap train-val kecil dan stabil → tidak ada tanda overfitting.

## Rekonstruksi & KL

| Metrik | Nilai akhir (epoch 100) |
|---|---|
| train_recon | ±0.44–0.46 (MSE per elemen, lihat CSV) |
| train_kl | mendekati capacity 0.5 |
| best_val_total | 0.948609 |

Catatan metodologis: nilai absolut loss TIDAK dibandingkan langsung dengan model
lama karena scaler berbeda (full-fit vs train-only). Perbandingan apples-to-apples
dilakukan pada metrik deteksi test (lihat 159).
