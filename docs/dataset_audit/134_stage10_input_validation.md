# 134 — Validasi Input Assembly (Tahap 10)

Input utama: `ai-service/dataset/encoded/audit_log_dataset_stage9_encoded_unscaled.csv`
SHA-256 `853c362859db26c9a3c1912addf6825bc3f8404da9d9939bff02fad747258055`.
Referensi silang: versi ter-skalasi Stage 9 `63801485…46affc`; Stage 8
`ce4854fa…ef959`; Stage 6 `5e9bf0d5…9e966` (semua tercatat Tahap 9).

## Audit metadata & artefak Stage 9

| Item | Hasil |
|---|---|
| stage9_metadata.json | feature_order cocok 9/9; label_mappings ada |
| stage9_label_encoders.pkl | loadable; kelas = activity 10 / status 2 / device 9 |
| stage9_scaler.pkl (candidate) | loadable; n_features_in_ = 9 |

## Validasi struktur input (detail di 137_stage10_final_matrix_validation.csv)

rows=15.000 · cols=9 · urutan fitur cocok kontrak · seluruh kolom numerik ·
NaN=0 · Inf=0 · alignment baris ke raw terverifikasi (user_id identik semua
baris; kode activity cocok mapping Stage 9 untuk seluruh 15.000 baris).

Input TIDAK diubah (read-only; checksum dicatat sebelum proses).
