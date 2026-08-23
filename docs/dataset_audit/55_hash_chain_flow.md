# 55 — Alur Hash Chain Audit Log (berdasarkan Source Code)

Sumber: `backend/services/auditLogService.js`, `backend/controllers/auditLogController.js`, `database/schema.sql`. Tidak ada perilaku yang diklaim di luar kode.

## Kolom (schema.sql:126-140)

`hash_sebelumnya CHAR(64)` (previous_hash) dan `hash_entri CHAR(64) NOT NULL` (current_hash). Keduanya hanya ada pada tabel `audit_log` — tidak ada padanannya di dataset synthetic maupun generator.

## Pembentukan chain — `createAuditLog` (auditLogService.js:7-82)

1. Ambil `hash_entri` baris terakhir (`ORDER BY id DESC LIMIT 1`) → menjadi `hashSebelumnya` (baris pertama rantai: NULL).
2. Susun string: `userId|aksi|targetTipe|targetId|waktu.toISOString()|hashSebelumnya`.
3. `hash_entri = SHA-256(string)` → INSERT baris baru beserta kedua hash.
4. Catatan penting: parameter `detail` (mis. `{expected, actual}` untuk POTENSI_ANOMALI_HASH_BERKAS atau stored/file hash untuk VERIFIKASI_INTEGRITAS_BERKAS) **tidak ikut di-hash dan tidak disimpan** — kolom INSERT tidak memuat detail.

Hubungan rekaman: `hash_entri(N)` == `hash_sebelumnya(N+1)`; input hash memuat `hashSebelumnya` sehingga perubahan baris lama memutus seluruh rantai berikutnya.

## Verifikasi chain — `verifyAuditChain` (auditLogService.js:148-201)

Loop semua baris urut `id`:

1. Jika `row.hash_sebelumnya !== previousHash` → return `{valid:false, brokenAt:id, reason:"Hash sebelumnya tidak sesuai"}`.
2. Rekomputasi SHA-256 dari field baris; jika ≠ `hash_entri` → return `{valid:false, brokenAt:id, reason:"Hash entri tidak sesuai"}`.
3. Jika lolos semua → `{valid:true, total:N}`.

Dipanggil melalui endpoint controller `verifyAuditLogs` (auditLogController.js:45-56, route dasar `/audit-log`). Tidak ditemukan di source code: penjadwalan otomatis, warning berkala, penolakan transaksi, rollback, atau recovery otomatis — verifikasi bersifat on-demand dan hasilnya hanya respons API.

## Deteksi & tindak lanjut

- **Deteksi perubahan log**: hanya saat endpoint verifikasi dipanggil (perubahan manual DB akan menghasilkan mismatch).
- **Logging**: tidak ada logging khusus atas kegagalan chain di dalam fungsi; kegagalan dilaporkan sebagai JSON response.
- **Recovery**: NOT_FOUND di source code.

## Hubungan dengan dataset

Dataset synthetic **tidak memiliki** kolom hash/previous-hash sama sekali (lihat `48_activity_file_schema_audit.csv`), sehingga mekanisme ini tidak terepresentasi dalam data latihan VAE.
