# 67 — Alur Manajemen Dataset (Metodologi)

```
DATASET AWAL (synthetic 15.000 baris + audit_log PostgreSQL 337 baris)
   input : generator/raw/audit_log_dataset.csv; tabel audit_log; source code
↓
AUDIT DATASET (Tahap 1)
   proses: inventaris, skema, kualitas, distribusi, integritas file, verifikasi klaim
   output: 01–14, reproducibility_notes
↓
VALIDASI SOP (Tahap 2a)
   proses: pemetaan aktivitas/role terhadap bukti kode & log (dokumen SOP nihil → NEEDS_VERIFICATION)
   output: 19, 20, 31, 32
↓
VALIDASI OPERASIONAL (Tahap 2b)
   proses: jam kerja, weekend, synthetic-vs-real, gap analysis
   output: 21–23, 26–30, 27/28
↓
AUDIT TEMPORAL (Tahap 3)
   proses: distribusi jam/tanggal/hari, kalender SKB 2025, matriks hari×jam, logika generator
   output: 33–47
↓
AUDIT AKTIVITAS/FILE/PATH/HASH (Tahap 4)
   proses: kosakata aktivitas, objek, path, mekanisme hash, hash chain, pemisahan integrity vs VAE
   output: 48–63
↓
DECISION MATRIX (Tahap 5)
   proses: klasifikasi temuan (MUST_FIX … NOT_RELEVANT_TO_VAE), keputusan berbasis evidence
   output: 64–70
↓
CLEANING RULES (Tahap 5)
   proses: penyusunan RULE A–P dengan status approved/deferred/protective
   output: 65, 66
↓
TAHAP 6: IMPLEMENTASI PERBAIKAN
   proses: eksekusi hanya aturan approved (mayoritas protektif/validasi); salinan Stage 6
   output: 71–99 + dataset salinan identik
```

Prinsip: AUDIT ≠ CLEANING, VALIDASI ≠ CLEANING, DECISION MAKING ≠ CLEANING. Tidak ada perubahan row-level sebelum Tahap 6, dan pada Tahap 6 pun hanya tindakan yang disetujui Tahap 5 yang boleh dieksekusi.
