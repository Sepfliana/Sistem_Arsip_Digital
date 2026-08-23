# 165 — End-to-End & Parity Validation (Tahap 12)

Hasil `audit_m_stage12.py`: **21 PASS / 0 FAIL** (`t12_checks.csv`).

## E2E (raw → preprocessing → 9 fitur → scaling → model → threshold → prediksi)

- Unscaled vector shape (1,9); seluruh nilai finite; urutan fitur sesuai tuple kontrak.
- IP tidak lagi 0 default (record uji: integer 32-bit non-nol).
- Scaling memakai final_train_scaler.pkl.
- Model kandidat loadable; threshold loadable = 3.0499422550201416.
- Output prediksi valid & lolos skema `PredictResponse`.

## Parity test terhadap data Stage 10/11

15 baris sampel (tiap split: awal/tengah/akhir + 2 anomali) direkonstruksi dari
raw Stage 6 → preprocessing inference baru:

| Pemeriksaan | Hasil |
|---|---|
| Vektor unscaled == baris stage9_encoded_unscaled.csv | identik (array_equal) 15/15 |
| Hasil scaling == X_train/validation/test_final.npy posisi bersesuaian | allclose atol 1e-6 · 15/15 |

→ Record raw yang sama menghasilkan representasi yang persis sama antara
training-side dan inference-side. **IP inference parity blocker: RESOLVED**
pada jalur kandidat.

## Contract negative tests

| Input | Perilaku |
|---|---|
| "999.999.1.1" | ValueError (ditolak) |
| "::1" (IPv6) | ValueError — tidak dipetakan ke nilai artifisial |
| activity "Klik Sembarang" | ValueError + daftar kelas valid |
| device "Smart Fridge" | ValueError + daftar kelas valid |
