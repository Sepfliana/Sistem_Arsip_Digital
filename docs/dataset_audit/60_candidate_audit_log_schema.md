# 60 — Kebutuhan Atribut Dataset Audit Log (REKOMENDASI — BELUM DITERAPKAN)

Rancangan atribut bila dataset ingin merepresentasikan audit log secara lebih realistis. **Bukan semua atribut menjadi input VAE** — pemisahan peran dinyatakan eksplisit di tiap bagian.

## A. Atribut wajib (identitas kejadian)

- `timestamp` dengan zona waktu eksplisit;
- `user_id` + `role` (FK users);
- `activity` — kamus mengikuti aksi backend yang benar-benar terlog (`createAuditLog`);
- `status`;
- `target_tipe`, `target_id` (objek logis: BERKAS, USER, PEMINJAMAN, ...);
- `session_id`.

Peran: identitas & konteks; sebagian menjadi fitur VAE setelah encoding.

## B. Atribut pendukung

- `ip_address` asli dari request (bukan default 'unknown');
- `device`/User-Agent asli;
- `duration_ms` hasil pengukuran nyata;
- `jumlah_objek` faktual per transaksi.

Peran: fitur perilaku VAE — **hanya jika sumbernya benar-benar mengisi nilai**, bukan konstanta default seperti kondisi saat ini.

## C. Atribut khusus integritas

- `hash_entri` / `hash_sebelumnya` (rantai log);
- `file_hash_sha256` (isi berkas), `path_file`, `nama_file`, `ukuran`;
- `status_integritas`; pasangan `sha256_database` vs `sha256_hasil` dari verifikasi.

Peran: **BUKAN input VAE**. Dipakai untuk HASH INTEGRITY DETECTION deterministik dan evaluasi forensik. Menyimpan hash sebagai fitur model tidak bermakna statistik dan berisiko bocor identitas objek.

## D. Atribut untuk VAE (input model)

Fitur numerik/kategorikal turunan saja, konsisten dengan kontrak 9-fitur saat ini: jam (`hour`), hari (`day_of_week`) dari timestamp; durasi; jumlah objek; kategori activity/status/device/ip. Identitas mentah (user_id mentah, path, hash) tidak direkomendasikan langsung masuk model.

## E. Atribut evaluasi / ground truth (bukan training)

- `anomaly_type`, `risk_level` (label generator);
- label verifikasi integritas (VALID/HASH TIDAK SESUAI);
- keputusan anomali (DITERIMA/OVERRIDE/SELESAI).

Peran: hanya untuk evaluasi kuantitatif dan analisis; wajib dipisahkan dari fitur agar tidak terjadi label leakage.

## Status

Seluruh butir adalah REKOMENDASI desain. Dataset, generator, skema database, dan source code aplikasi TIDAK diubah pada tahap ini.
