# 95 — Pemisahan Synthetic vs Real (RULE P)

## Keputusan Tahap 5 yang dieksekusi

- **Training**: hanya `ai-service/dataset/generator/raw/audit_log_dataset.csv` (15.000 baris synthetic) → working copy Stage 6 identik.
- **Real PostgreSQL audit_log (337 baris)**: TIDAK masuk training. Fungsinya: *external validation / behavioral reference / schema validation* (matriks baris 31, DO_NOT_FIX).

## Verifikasi

1. Pipeline aktif (`preprocessing.py`) membaca CSV generator — tidak ada jalur query DB ke training set.
2. File retraining lama TIDAK dipakai sebagai sumber perubahan: `retraining_dataset_combined_raw.csv`, `retraining_dataset_canonical.csv`, `X_train_candidate.npy` dibiarkan utuh (tidak dibaca, tidak dimodifikasi) — aturan Tahap 5 tidak menyetujui penggunaannya.
3. `git status`: tidak ada perubahan pada ai-service kecuali penambahan file Stage 6 yang diinstruksikan.
4. `X_train.npy` tetap (15000, 9).

## Kondisi real saat ini (pembanding, dari Tahap 4/58)

337 baris · 33 aksi · 100% target_tipe/target_id terisi · hash chain utuh · IP/device 'unknown' 333/337 · dominasi trafik uji — alasan metodologis mengapa ia bukan training.

Status: **SEPARATION ENFORCED**.
