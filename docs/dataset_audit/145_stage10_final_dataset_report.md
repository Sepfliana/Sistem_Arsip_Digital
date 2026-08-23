# Stage 10 — Final VAE Dataset Assembly Report

## 1. Tujuan
Membentuk dan memvalidasi dataset final input Tahap 11 — tanpa retraining,
threshold tuning, deployment, atau perubahan artefak sumber mana pun.

## 2. Input
Stage 9 encoded unscaled (SHA `853c3628…58055`) + metadata/encoder/scaler pkl +
laporan 122–133. Checksum semua tercatat (`134`).

## 3. Input Validation
15.000×9, urutan kontrak, numerik penuh, NaN=0, Inf=0, alignment ke raw PASS,
artefak Stage 9 loadable (`134`, `137`).

## 4. Feature Contract
9 fitur kontrak, urutan identik metadata Stage 9 = urutan model aktif (n,9).
Tidak ada discrepancy urutan ditemukan.

## 5. Label Separation
anomaly_type/risk_level tidak masuk matrix; dipertahankan di companion CSV
per split untuk evaluasi (`135`).

## 6. Synthetic/Real Separation
Seluruh baris berasal dari generator; real PostgreSQL 337 record TIDAK digabung;
retraining_dataset_combined_raw.csv & artefak real lama tidak disentuh.

## 7. Dataset Splitting
Tidak ada split existing → keputusan baru: group-based by session_id, seed 42,
70/15/15 → train 10.503 / validation 2.266 / test 2.231; sesi utuh antar-split
(`136`). Distribusi label proporsional (~10% anomali tiap split).

## 8. Leakage Control
Cross-split exact-row overlap = 0/0/0; 0 sesi menyeberang; setiap baris tepat
satu split; label/hash/path tidak ada di matrix (`139`).

## 9. Scaling Decision
**Opsi B**: FINAL TRAINING SCALER baru, StandardScaler fit HANYA train
(10.503 baris) → `dataset/final/scaler/final_train_scaler.pkl` + parameter di
metadata. Alasan: kontrol leakage metodologis; scaler Stage 9 (fit full-data)
tetap utuh sebagai candidate/historis dan TIDAK dipakai untuk final matrix.

## 10. Final Feature Matrix
X_train (10503,9), X_validation (2266,9), X_test (2231,9) — float32, urutan
kontrak, tanpa fitur konstan.

## 11. Label Distribution
Train: normal 9.454 / anomali 1.049 (9,99%); Validation: 2.030/236 (10,41%);
Test: 2.016/215 (9,64%). Detail per anomaly_type & risk_level: `138`.

## 12. Temporal Distribution
Semua karakteristik kalender TERPRESERVASI di tiap split — working 8.180/1.706/1.747;
before-08 1.268/302/284; after-16 1.055/258/200; weekend 2.930/683/585;
holiday 800/131/193 (`140`). Tidak ada yang dihapus; bukan label anomali otomatis.

## 13. Feature Distribution
Per split × 9 fitur min/max/mean/median/std: `141`; tidak ada fitur konstan.

## 14. Validation Results
Quality gate script: **28 PASS / 0 FAIL** (`137`).

## 15. IP Inference Blocker
**OPEN BLOCKER FOR DEPLOYMENT / INFERENCE** — sengaja tidak diperbaiki di sini.
Status terpisah: *dataset training SIAP untuk Tahap 11*, tetapi *pipeline
training-to-inference BELUM siap* hingga parity IP/vocab/log1p/timezone
diselesaikan (Tahap 11–12).

## 16. Reproducibility
Seed 42; script deterministik; checksum output npy tercatat (`143`).

## 17. Final Dataset Files
`ai-service/dataset/final/`: X_train_final.npy, X_validation_final.npy,
X_test_final.npy, final_dataset_metadata.json, scaler/final_train_scaler.pkl,
train/validation/test_metadata.csv.

## 18. Limitations
1. Group split (bukan stratified eksplisit) — proporsi label tetap stabil.
2. Scaler final berbeda dari scaler produksi lama → model lama tidak kompatibel
   dengan matrix ini tanpa retraining (memang tujuan Tahap 11).
3. Parity inference masih BLOCKER terbuka.

## 19. Conclusion
Final VAE dataset assembly **berhasil**: tiga matrix float32 valid, leakage
terkendali, checksum & reproducibility lengkap — **siap menjadi input resmi
Tahap 11**.
