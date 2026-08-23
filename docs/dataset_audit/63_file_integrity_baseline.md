# 63 — Baseline Integritas File & Aktivitas (pra-perbaikan)

Angka aktual hasil audit Tahap 4 — acuan wajib pembanding sebelum/sesudah perbaikan apa pun.

## Aktivitas

| Indikator | Synthetic | Real (audit_log) |
|---|---|---|
| Total record | 15000 | 337 |
| Jenis aktivitas unik | 10 | 33 |
| Aktivitas dengan objek teridentifikasi (target/id) | 0 | 337/337 |
| Event berobjek BERKAS | 0 | 69 |

## Path & file

| Indikator | Nilai |
|---|---|
| Kolom path/filename di synthetic | 0 (NOT_FOUND) |
| Kolom path/filename di audit_log real | 0 (NOT_FOUND) |
| Tabel `berkas`: total baris | 3 |
| Baris ber-hash_sha256 | 3 |
| Baris ber-path_file | 3 |
| Path unik | 3 |
| Path berulang (baris >1 per path) | 0 |
| Kelompok path sama + hash berbeda | 0 |

## Hash

| Indikator | Nilai |
|---|---|
| hash_entri (current) di audit_log real | 337/337 (100%) |
| hash_sebelumnya (previous) di audit_log real | 336/337 — 1 NULL = kepala rantai |
| file hash SHA-256 di audit_log / synthetic | 0 — hanya di tabel berkas |
| Riwayat verifikasi integritas (`verifikasi_integritas_berkas`) | 1 entri, status VALID |
| status_integritas berkas | VALID 1 · BELUM_DIVERIFIKASI 2 |

## Event tanpa informasi integritas

| Dataset | Event | % dari total |
|---|---|---|
| Synthetic (tanpa kolom integritas apa pun) | 15000/15000 | 100% |
| Real: selain VERIFIKASI_INTEGRITAS_BERKAS (4) dan POTENSI_ANOMALI_HASH_BERKAS (0) | 333/337 | 98,8133% |

Catatan klasifikasi: "informasi integritas" pada level log = keberadaan aksi verifikasi/potensi-anomali atau nilai hash; hash chain hadir di SEMUA baris real tetapi merupakan integritas jejak audit, bukan integritas isi file. Dataset tidak diubah — baseline ini titik nol pra-perbaikan.
