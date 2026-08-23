# Stage 9 — Encoding & Scaling Report

## 1. Tujuan
Mengubah 9 canonical features Stage 8 menjadi representasi numerik konsisten
untuk VAE, mengikuti kontrak training existing — tanpa feature engineering baru,
tanpa menyentuh dataset sumber/source aplikasi/model.

## 2. Input Dataset
`ai-service/dataset/feature_engineering/audit_log_dataset_stage8_features.csv`
(15.000×9; SHA-256 `ce4854fa…ef959`). Rantai preservasi ke Stage 6 terverifikasi.

## 3. Existing Preprocessing Audit
Training (`preprocessing.py`): LabelEncoder×3, IP→integer, passthrough numerik,
StandardScaler, output (n,9), artefak dipersist di `dataset/preprocessed/`.
Inference (`utils/preprocessing_contract.py`): mapping kanonik berbeda, log1p,
timezone WIB, ip_encoded konstan 0 (kunci encoder tidak ada). Detail: `122`.

## 4. Discrepancy Resolution
D1 RESOLVED (kode = 9 fitur; doc usang). D2: IP parity = BLOCKER utk deployment;
log1p & timezone = WARNING → DECISION saat retraining. D3: kosakata sintetis 10
dipakai utk dataset ini; kanonik tetap dokumentasi. Tidak ada source diubah. `123`.

## 5. Encoding Contract
Per-fitur pada `124`; dimensi total tetap 9 (semua transform satu-kolom).

## 6. Feature Transformations
- user_id: int64 passthrough (keputusan: dipertahankan — evidence kedua pipeline
  existing memperlakukan numerik; kandidat kategorikal ditunda, bukan preferensi).
- activity/status/device: LabelEncoder alphabetical; roundtrip decode identik.
- ip_address: `int(ipaddress.ip_address())`; roundtrip string identik.
- duration_ms/object_count/hour/day_of_week: float64 passthrough (tanpa log1p;
  tanpa cyclical — tidak ada evidence di source).

## 7. Scaling Contract
StandardScaler fit pada seluruh 15.000 baris (mengikuti pipeline existing).
Parameter mean_/scale_/var_ tersimpan. **Catatan jujur**: final split belum ada
(Tahap 10) → scaling ini adalah *preprocessing candidate* terhadap sumber data
training; klaim leakage-free fitting tidak dibuat.

## 8. Feature Order
user_id, activity, status, device, ip_address, duration_ms, object_count, hour,
day_of_week — posisi raw→encoded→final di `126`.

## 9. Numeric Validation
14/14 PASS (`125`): numerik penuh, tanpa NaN/Inf, dtype float64 seragam, urutan
deterministik, 15.000 baris, scaler mean≈0/std≈1, roundtrip exact, sumber tak berubah.

## 10. Train/Inference Compatibility
**BLOCKER (terdokumentasi)** pada channel IP (inference konstan 0); WARNING pada
activity/device vocab, log1p, timezone. Tidak menghalangi dataset training-side.
Resolusi wajib di Tahap 11–12. `129`.

## 11. Leakage Validation
0 label/hash/path/target leakage (`130`). Kontrol split final = Tahap 10.

## 12. Output Dataset
- `ai-service/dataset/encoded/audit_log_dataset_stage9_encoded.csv`
  (15.000×9 float64; SHA-256 `63801485f5e5c84dbe4453d214f811de62c75b8efd1e53bb917664303846affc`)
- `..._unscaled.csv`, `stage9_label_encoders.pkl`, `stage9_scaler.pkl`,
  `stage9_metadata.json`

## 13. Limitations / Warnings
1. IP ordinal + skew ekstrem (internal vs publik) — karakteristik kontrak existing.
2. Parity inference BLOCKER menunggu keputusan retraining.
3. Scaler fit full-data sebelum split final (mengikuti existing; dicatat).
4. user_id ordinal risk dipertahankan demi kesetiaan pada sistem existing.

## 14. Kesimpulan
Encoding & scaling **berhasil**; dataset numerik intermediate **berhasil dibuat**
(14/14 PASS). Terdapat 1 BLOCKER parity inference + beberapa WARNING yang sudah
terdokumentasi — semuanya tidak menghalangi tahap berikutnya namun WAJIB jadi
bahan keputusan Tahap 10–12. Dataset **siap untuk Tahap 10** (final assembly),
dan TIDAK disebut final VAE dataset.
