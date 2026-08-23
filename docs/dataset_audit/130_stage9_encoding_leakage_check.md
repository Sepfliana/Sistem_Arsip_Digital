# 130 — Encoding Leakage Check (Tahap 9)

## Pemeriksaan pada input Stage 8 dan output encoded

| Jenis leakage | Kolom terkait | Ada di input? | Masuk encoding? | Status |
|---|---|---|---|---|
| label leakage | anomaly_type, risk_level | ya (di raw Stage 6, tidak dibawa ke Stage 8) | tidak | PASS |
| label turunan | is_anom, skor_anomali, tingkat_risiko | tidak pernah dibuat | tidak | PASS |
| hash leakage | hash/previous_hash/current_hash | tidak ada | tidak | PASS |
| path leakage | path/filename/file | tidak ada | tidak | PASS |
| target leakage | target_tipe/target_id | tidak ada | tidak | PASS |

Bukti otomatis: check `label_hash_path_leakage` di
`125_stage9_numeric_validation.csv` = PASS (0 istilah terlarang pada 9 kolom output).

## Catatan metodologis

1. Label ground truth tetap berada di raw Stage 6 untuk evaluasi Tahap 11 —
   pemisahan ini disengaja (bukan bagian fitur).
2. Scaler di-fit pada seluruh 15.000 baris mengikuti pipeline existing;
   **klaim leakage-free split belum dapat dibuat** — final split & kontrol
   leakage ditetapkan Tahap 10 (lihat 133 §7).
3. Tidak ada statistik label yang digunakan untuk menentukan mapping encoder
   (LabelEncoder murni alphabetical).
