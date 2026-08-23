# 162 — Analisis Distribusi Reconstruction Error (bahan Bab Hasil/Pembahasan)

Model: retrained best-val (epoch 99) · Threshold: 3.04994 (P95 train) ·
Overlap = histogram intersection normal vs anomali.

## Statistik per split (dari 153_stage11_reconstruction_error.csv)

| Scope | Group | n | Mean | Median | Std | P95 | P99 |
|---|---|---|---|---|---|---|---|
| train | Normal | 9454 | 0.6822 | 0.5772 | 0.5844 | 1.1655 | 3.9229 |
| train | Anomaly | 1049 | 3.2854 | 1.2041 | 6.7002 | 11.8284 | 29.0693 |
| validation | Normal | 2030 | 0.6990 | 0.6037 | 0.5708 | 1.1915 | 3.9661 |
| validation | Anomaly | 236 | 3.0539 | 1.3271 | 3.9720 | 10.9673 | 17.2649 |
| test | Normal | 2016 | 0.6635 | 0.5603 | 0.5720 | 1.1183 | 3.8167 |
| test | Anomaly | 215 | 3.5103 | 1.2559 | 5.6183 | 11.3355 | 26.9966 |

Rasio mean error anomali:normal konsisten ±4.4–5.3× di semua split.

## Overlap & implikasi FP/FN

| Split | Overlap | FP | FN |
|---|---|---|---|
| validation | 0.6525 | 51 | 171 |
| test | 0.7116 | 52 | 149 |

- **FN dominan**: threshold P95-train (±flag 5%) lebih rendah dari median
  banyak jenis anomali "halus" → sebagian besar login_luar_jam /
  aktivitas_terlalu_cepat / device_berubah lolos (deteksi <10%).
- **FP kecil**: specificity tinggi (0.974–0.975); FP berasal dari normal
  berekstrem (duration/object_count outlier yang secara statistik mirip
  pola anomali massal).
- Distribusi ekor panjang: max error anomali mencapai 46.9 (test) — outlier
  massal sangat mudah terdeteksi; justru anomali bernilai dekat normal yang sulit.

Kesimpulan analisis: VAE efektif menangkap anomali berimpak besar (verifikasi_
massal ±92%, peminjaman_massal ±56%, ip_berubah ±62%) namun terbatas untuk
anomali subtil pada fitur kategorikal yang ter-encoded ordinal — limitation
metodologis dataset, bukan kegagalan prosedur Tahap 11.
