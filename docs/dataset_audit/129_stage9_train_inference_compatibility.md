# 129 — Training / Inference Compatibility (Tahap 9)

Perbandingan berbasis source code (bukan asumsi). Validator manual terdokumentasi;
tidak ada source yang diubah.

| Aspek | Training (`preprocessing.py`) | Inference (`utils/preprocessing*.py`) | Konsisten? |
|---|---|---|---|
| Feature order | FEATURE_COLUMNS 9 | DataFrame 9 kolom urutan sama | PASS |
| Output dimensi | (n,9) float64 | (1,9) float32; model menuntut 9 | PASS dimensi (dtype beda: cast internal) |
| activity mapping | LabelEncoder vocab mentah 10 | canonical 12 kelas → encoder mentah tak kenal kelas kanonik → jatuh ke fallback UNKNOWN/case-insensitive/0 | **MISMATCH** |
| status mapping | LabelEncoder Berhasil/Gagal | canonical Berhasil/Gagal (+UNKNOWN) — nama cocok | PASS |
| device mapping | LabelEncoder 9 variasi | parse UA → 7 kelas kanonik ("PC Windows" cocok; "Windows"/"Laptop Windows"/"iPhone" tidak) | **PARTIAL MISMATCH** |
| IP handling | integer 32-bit masuk scaler | `ip_address` tidak ada di encoders.pkl → ip_encoded = 0 konstan | **BLOCKER** |
| duration/object_count | mentah → scaler | log1p → scaler yang sama | **MISMATCH skala** |
| hour/day_of_week | naive lokal | naive dianggap UTC → WIB (−7 jam) | **MISMATCH zona waktu** |
| unknown handling | tidak ada mekanisme | fallback UNKNOWN/0 diam-diam | WARNING |
| Scaler | StandardScaler dipersist | memakai pkl sama | PASS |

## Verdict

- **Feature order & dimensi & scaler artefak**: PASS.
- **Status channel**: PASS.
- **IP channel**: BLOCKER — inference mustahil mereproduksi representasi training
  (konstan 0 vs integer besar); parity serving rusak pada fitur ini.
- **Activity/device/duration/log1p/timezone**: WARNING terdokumentasi
  (menurunkan akurasi parity tapi tidak menghalangi pembentukan dataset training).

Kesimpulan: dataset intermediate Tahap 9 konsisten dengan jalur TRAINING.
Parity TRAINING↔INFERENCE = **BLOCKER (terdokumentasi)** yang WAJIB diselesaikan
pada Tahap 11 (retraining dengan kontrak tunggal) / Tahap 12 (deployment),
mis. dengan mengadopsi `preprocessing_contract.py` di kedua sisi + retrain +
re-threshold. Bukan cakupan Tahap 9 untuk memperbaikinya.
