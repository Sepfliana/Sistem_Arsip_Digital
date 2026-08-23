# 169 — Final Deployment Readiness Report (Tahap 12 — FINAL)

## Status akhir

**CANDIDATE INTEGRATED / PRODUCTION MODEL UNCHANGED**

Model retrained Stage 11 sudah terintegrasi penuh ke aplikasi melalui endpoint
kandidat terpisah `/predict-stage11`, tervalidasi end-to-end. Model produksi
`/predict` TIDAK diganti (masih `vae_model.pth` + threshold 3.1496288776397705);
klaim deployment aktif hanya berlaku untuk jalur kandidat.

## Bukti kualitas (quality gate Tahap 12)

| Gate | Hasil |
|---|---|
| `audit_m_stage12.py` (contract/parity/E2E/regresi) | 21 PASS / 0 FAIL |
| `audit_n_stage12.py` (wiring/endpoint/negative/safety) | 24 PASS / 0 FAIL |
| **Total** | **45 PASS / 0 FAIL** |

- IP parity: RESOLVED (integer IPv4 identik training-side; invalid/IPv6 → HTTP 400).
- Encoder parity: LabelEncoder asli Stage 9 (10/2/9), unknown → 400.
- Scaler parity: final_train_scaler.pkl fit TRAIN-only.
- Parity raw→training representation: 15/15 baris identik + scaling allclose.
- Threshold kandidat tidak diubah: 3.0499422550201416.

## Cutover (opsional, di luar cakupan roadmap)

Jika kelak diputuskan controlled cutover: promosikan `models/retrained/*`
menjadi artefak produksi, arahkan `/predict` ke jalur Stage 11, dan pertahankan
jalur lama sebagai fallback — seluruh prasyarat teknis telah tervalidasi.

## Artefak Tahap 12

- Kode: `ai-service/services/inference_stage11.py` (baru),
  `ai-service/app.py` (+rute kandidat).
- Test: `docs/dataset_audit/audit_m_stage12.py`, `audit_n_stage12.py`,
  `t12_checks.csv`, `t12b_checks.csv`, `t12_stats.json`.
- Laporan: 163–169.
