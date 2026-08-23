# 68 — Tabel Metodologi Skripsi: Manajemen Dataset

| Tahap | Input | Proses | Metode | Output | Dasar Keputusan |
|---|---|---|---|---|---|
| Audit kondisi awal (T1) | CSV generator, tabel audit_log, source code, model artifacts | Inventarisasi & profil | Statistik deskriptif, inspeksi skema/kode, query SELECT-only | 01–14, baseline angka | Bukti empiris file & DB |
| Validasi SOP (T2) | Hasil T1 + controllers backend | Pemetaan aktivitas/role/jam vs bukti kode | Cross-reference grep + JOIN DB | 19–20, 29–32 | Source code = satu-satunya dasar tersedia; dokumen SOP nihil → NEEDS_VERIFICATION |
| Validasi operasional (T2) | idem | Perbandingan synthetic vs real | Agregasi komparatif tanpa penggabungan | 21–28, 30 | Angka audit kedua dataset |
| Audit temporal (T3) | Kolom timestamp | Distribusi jam/hari/tanggal, kalender, matriks hari×jam | Analisis analitis read-only + verifikasi SKB 2025 eksternal resmi | 33–47 | Timestamp + kalender SKB (setkab.go.id) |
| Audit aktivitas/file/path/hash (T4) | Kedua dataset + backend code + tabel berkas | Kosakata, objek, path, hashing, chain | Inspeksi kode + query read-only | 48–63 | Fakta kode & skema; pemisahan HASH INTEGRITY vs VAE ANOMALY |
| Perumusan aturan (T5) | Semua output audit | Klasifikasi temuan & keputusan | Decision matrix evidence-based | 64–70 | Baris matriks 1–40 dgn confidence |
| Implementasi (T6) | Dataset utama + aturan T5 | Eksekusi aturan approved (protektif) + validasi | Salinan terkontrol-checksum, scan duplikat, verifikasi kontrak | 71–99, salinan Stage 6 identik | RULE A–P status approved |

Catatan eksplisit: kolom "Proses" menunjukkan tahap 1–5 adalah audit/validasi/keputusan — cleaning implementatif baru terjadi pada Tahap 6, dan bahkan di sana mayoritas aturan bersifat protektif (tidak mengubah row-level).
