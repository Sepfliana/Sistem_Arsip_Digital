# 154 — Metode Threshold (Tahap 11)

## Audit existing

Threshold produksi = P95 reconstruction error TRAIN model lama
(`services/inference.py:43` → `deployment_config.json` = 3.14963).

## Keputusan Tahap 11

Metodologi yang sama dihitung ulang dengan model baru:

- **Threshold baru = P95 dari reconstruction error TRAIN** (10.503 baris,
  model best-val) → **3.0499422550201416**.
- Disimpan terpisah: `models/retrained/stage11_threshold.json`.
- `models/deployment_config.json` TIDAK disentuh.

## Referensi (tidak dipakai seleksi)

- Validation P95 = 3.226661 — hanya direkam sebagai referensi.
- **TEST tidak digunakan dalam seleksi threshold sama sekali**
  (struktural: threshold dihitung sebelum evaluasi test; lihat 157).

## Konsekuensi metodologis

P95-train menempatkan flag rate ±5% sementara prevalensi anomali 10% → recall
secara desain dibatasi (~0.28–0.31). Ini konsisten dengan perilaku sistem
existing; perubahan strategi threshold (mis. berbasis validasi) = DECISION
terpisah untuk deployment, bukan cakupan retraining ini.
