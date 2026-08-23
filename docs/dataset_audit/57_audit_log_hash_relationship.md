# 57 — Hubungan Audit Log dengan Hash

## Apa yang dicatat audit_log (faktual, dari INSERT auditLogService.js:48-82)

| Item | Dicatat? | Keterangan |
|---|---|---|
| hash sebelum perubahan / previous_hash | **YA** | kolom `hash_sebelumnya` = hash_entri baris sebelumnya (rantai log) |
| hash sesudah perubahan / current_hash | **YA** | kolom `hash_entri` = SHA-256 entri itu sendiri (rantai log) |
| file hash (SHA-256 isi berkas) | **TIDAK** | tersimpan di `berkas.hash_sha256`, tidak pernah masuk audit_log |
| integrity verification result | **SEBAGIAN** | hanya untuk aksi VERIFIKASI_INTEGRITAS_BERKAS: status kolom `status` = "VALID"/"HASH TIDAK SESUAI"; hasil detail (pasangan hash) masuk tabel `verifikasi_integritas_berkas`, bukan audit_log |
| aktivitas pengguna | **YA** | user_id, aksi, target_tipe, target_id, waktu, durasi, jumlah objek, ip, device |

## Sifat hash pada audit log

Hash di audit_log adalah **hash rantai entri** (integritas jejak audit), bukan hash konten file. Input hash = `userId|aksi|targetTipe|targetId|waktu.toISOString()|hashSebelumnya`. Tidak ada hubungan kriptografis antara `audit_log.hash_entri` dan isi berkas.

## Peristiwa yang menghubungkan dunia file-hash dengan audit log

1. **POTENSI_ANOMALI_HASH_BERKAS** — dibuat saat download mendeteksi mismatch (detail expected/actual dikirim namun TIDAK tersimpan).
2. **VERIFIKASI_INTEGRITAS_BERKAS** — dibuat setiap verifikasi manual; status integritas terbawa ke kolom status.
3. **CREATE_BERKAS / UPDATE_BERKAS** — upload/update menghitung & menyimpan hash baru di `berkas`, tetapi nilai hash tidak terekam di audit_log.

## Jika ditanya "apakah audit log merepresentasikan integritas berkas?"

Jawaban faktual: **hanya secara indirekt melalui aksi/status**, bukan melalui nilai hash. Dataset synthetic bahkan lebih tipis: tidak memiliki kolom hash/path/file sama sekali (lihat 48), sehingga seluruh mekanisme ini tidak terepresentasi dalam data latihan VAE.

## Data real sebagai bukti (337 record)

- `hash_entri`: 337/337 terisi · `hash_sebelumnya`: 336/337 (1 NULL = kepala rantai).
- Kolom path/filename/hash-file di audit_log: NOT_FOUND.
- Status VALID berasal dari aksi VERIFIKASI_INTEGRITAS_BERKAS (lihat 58).
