# 152 — Model Quality (Tahap 11)

## Konvergensi

- Train loss epoch-100: 0.960861 (recon 0.944569, KL 0.516293).
- Best validation loss: 0.948609 @ epoch 99; epoch-100 val 0.955615.
- KL mengikuti target capacity (0.5) → latent terpakai informatif.

## Overfitting / Underfitting

- Val loss < train loss dan gap kecil → tidak overfitting.
- Val loss masih menurun tipis di akhir budget → underfitting ringan
  (budget 100 epoch existing dipertahankan demi kesetiaan konfigurasi).

## Kualitas deteksi (bukan sekadar loss rendah)

| Sinyal | Nilai |
|---|---|
| Recon error Normal test | mean 0.6635 / median 0.5603 / p95 1.1183 |
| Recon error Anomali test | mean 3.5103 / median 1.2559 / p95 11.3355 |
| Rasio mean anomali:normal (test) | ±5.3× — pemisahan ada tapi tumpang-tindih |
| Histogram overlap (test) | 0.7116 → **overlap besar = limitation utama** |
| F1 test @ threshold P95-train | 0.3964 |

Kesimpulan kualitas: model BELAJAR (anomali jelas lebih sulit direkonstruksi),
namun distribusi error normal vs anomali overlap besar sehingga threshold tunggal
tidak dapat memisahkan sempurna. Loss lebih kecil dari model lain TIDAK dijadikan
klaim superioritas — perbandingan sah hanya pada metrik deteksi (159).
