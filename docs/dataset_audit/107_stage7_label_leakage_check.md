# 107 — Pemeriksaan Label Leakage Stage 7

## Status label pada dataset tervalidasi

| Label | Ada di raw CSV? | Di FEATURE_COLUMNS? | Keputusan |
|---|---|---|---|
| anomaly_type | Ya (dipertahankan sbg ground truth) | TIDAK | bersih |
| risk_level | Ya (idem) | TIDAK | bersih |
| is_anom | Tidak ada pada dataset ini | TIDAK | tidak dibuat — sesuai instruksi |
| skor_anomali / tingkat_risiko | Hanya tabel DB laporan_anomali | TIDAK | post-event output model |

## Bukti

- Parse kontrak (`preprocessing.py` → FEATURE_COLUMNS) = 9 fitur perilaku; tidak memuat nama label apa pun.
- Dry-run in-memory Tahap 7 menggunakan hanya FEATURES9; label tidak pernah masuk matriks fitur.
- Forbidden-term scan atas kontrak: hash/path/target/label = **0 temuan**.

## Kesimpulan

**LABEL LEAKAGE = 0.** Ground truth tetap tersedia untuk evaluasi tanpa menjadi input model.
