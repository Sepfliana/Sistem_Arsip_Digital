# 56 — Analisis Deteksi "File Diganti, Path Tetap" (berdasarkan Source Code)

Sumber: `backend/controllers/berkasController.js` (fungsi `calculateFileHash`, `getBerkasFile`, `verifyBerkasIntegrity`) + skema `berkas` (schema.sql:91-113). Ini **HASH INTEGRITY DETECTION** — deterministik, berbasis kriptografi.

## Jawaban atas pertanyaan wajib

1. **Apakah path merupakan identitas file?** TIDAK. Path (`berkas.path_file`) hanya lokasi fisik; identitas konten dianchor oleh `hash_sha256` hasil SHA-256 isi file. Kode membaca file dari path lalu meng-hash isinya — dua file berbeda pada path sama akan menghasilkan hash berbeda.
2. **Apakah hash dihitung dari isi file?** YA — `fs.readFileSync(filePath)` → `crypto.createHash("sha256").update(buffer)` (berkasController.js:10-17). Bukan hash metadata/path/nama.
3. **Jika file diganti tetapi path sama?** Saat upload/update baru: hash baru dihitung dan menimpa `berkas.hash_sha256` (baris 573, 707). Jika isi diganti di luar aplikasi (path sama): stored hash tidak ikut berubah → mismatch saat dibandingkan.
4. **Kapan perubahan terdeteksi?** Dua titik: (a) `getBerkasFile` — setiap percobaan download menghitung ulang hash dari disk (baris 856); (b) `verifyBerkasIntegrity` — verifikasi manual per berkas (baris 915). Tidak ada watcher/scheduler.
5. **Apakah sistem memberi warning?** YA. (a) Download: audit log `POTENSI_ANOMALI_HASH_BERKAS` + respons HTTP 409 *"Integritas file arsip berubah. Akses file diblokir."* beserta expected/actual hash — akses DIBLOKIR (baris 858-875). (b) Verifikasi manual: status_integritas = "HASH TIDAK SESUAI", pasangan hash disimpan di `verifikasi_integritas_berkas` (sha256_database vs sha256_hasil), plus audit log `VERIFIKASI_INTEGRITAS_BERKAS`.
6. **Komponen pemberi warning?** Backend — `berkasController.getBerkasFile` dan `berkasController.verifyBerkasIntegrity`; bukti tersimpan di tabel `audit_log`, `verifikasi_integritas_berkas`, dan kolom `berkas.status_integritas`.
7. **Apakah VAE terlibat?** TIDAK. Seluruh alur di atas murni perbandingan hash. VAE tidak menerima fitur hash/path/file (input 9 fitur perilaku) dan tidak dipanggil dalam alur integritas berkas.

## Pemisahan dua mekanisme (WAJIB terpisah)

| Aspek | HASH INTEGRITY DETECTION | VAE ANOMALY DETECTION |
|---|---|---|
| Dasar | Perbandingan SHA-256 isi file vs stored | Rekonstruksi VAE atas 9 fitur perilaku vs threshold |
| Sifat | Deterministik; deteksi pasti jika konten beda | Probabilistik; skor rekonstruksi |
| Trigger | Download / verifikasi manual / akses event | Setiap createAuditLog → POST /predict (auditLogService.js:101) |
| Output | Status VALID / HASH TIDAK SESUAI; blokir akses | ANOMALY/normal → insert `laporan_anomali` |
| Objek | Integritas FISIK berkas | Pola PERILAKU pengguna |

Catatan penamaan: aksi `POTENSI_ANOMALI_HASH_BERKAS` adalah temuan **hash integrity**, bukan keluaran VAE — meski namanya mengandung "ANOMALI".

## Batasan yang teridentifikasi

Nilai hash expected/actual yang dikirim ke `createAuditLog` melalui parameter `detail` **tidak tersimpan** di `audit_log` (kolom INSERT tidak memuat detail) — audit hanya mencatat bahwa kejadian terjadi, sedangkan bukti hash lengkap tersimpan di `verifikasi_integritas_berkas` untuk jalur verifikasi manual saja.
