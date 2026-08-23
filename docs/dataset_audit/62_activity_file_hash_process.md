# 62 — Proses Audit Aktivitas, File, Path, dan Hash

Seluruh proses bersifat AUDIT (read-only); tidak ada pembersihan/perbaikan/pembentukan dataset final.

1. **Identifikasi aktivitas.** Kolom `activity` (synthetic, 10 jenis) dan `aksi` (real, 33 jenis) diinventarisasi beserta distribusinya (`49`).
2. **Identifikasi objek/file.** Kolom objek diperiksa per aktivitas: synthetic hanya `object_count` numerik; real memiliki `target_tipe`/`target_id` 100% terisi; kolom file/path tidak ada pada kedua dataset (`51`, `48`).
3. **Identifikasi path.** Pencarian menyeluruh: NOT_FOUND di synthetic maupun audit_log; satu-satunya path nyata adalah `berkas.path_file` di database aplikasi (3 baris) (`52`).
4. **Identifikasi hash.** Penelusuran source code menemukan 5 mekanisme: rantai SHA-256 audit log, fingerprint SHA-256 isi berkas, bcrypt password, TOTP 2FA, dan skema penyimpanan hasil verifikasi (`54`).
5. **Audit perubahan path.** Level log: HASH_NOT_AVAILABLE_IN_SYNTHETIC_DATASET. Level aplikasi: identitas file = isi (hash), bukan path; mismatch terdeteksi saat download/manual verify dengan blokir akses dan pencatatan (`53`, `56`).
6. **Audit hash chain.** Alur pembentukan (`createAuditLog`) dan verifikasi (`verifyAuditChain` → endpoint `/audit-log`) ditelusuri baris-per-baris; tanpa auto-recovery/scheduler (`55`).
7. **Verifikasi mekanisme integritas.** Bukti empiris DB: 3 berkas ber-hash, status integritas VALID/BELUM_DIVERIFIKASI, riwayat verifikasi 1 entri VALID, 0 kejadian POTENSI_ANOMALI_HASH_BERKAS (`58`, `63`).
8. **Perbandingan synthetic dan real.** Dilakukan terpisah tanpa penggabungan: kosakata aktivitas, keberadaan objek, dan atribut integritas dibandingkan dua arah (`50`, `58`).
9. **Identifikasi gap.** Sembilan gap dikatalogkan dengan bukti, dampak, confidence, dan rekomendasi (`59`).
10. **Penyusunan kebutuhan atribut dataset.** Rancangan atribut A–E (wajib, pendukung, integritas, input VAE, ground truth) disusun sebagai REKOMENDASI — belum diterapkan (`60`).

Setiap langkah menghasilkan artefak terukur sehingga dapat direproduksi (skrip `audit_f_activity_file.py`, query read-only terdokumentasi, catatan lingkungan di `reproducibility_notes.md`).
