# 61 — Tabel Skripsi: Audit Aktivitas, File, Path, dan Hash

| No | Aspek | Sumber Data | Metode Audit | Hasil | Keterangan |
|---|---|---|---|---|---|
| 1 | Skema kolom aktivitas/objek/hash | Synthetic CSV + tabel audit_log + schema.sql | Inventarisasi kolom & semantic role | Synthetic 13 kolom tanpa file/path/hash; real 12 kolom dengan hash chain; file hash hanya di tabel berkas | `48_activity_file_schema_audit.csv` |
| 2 | Distribusi aktivitas | Kedua dataset (terpisah) | Agregasi per jenis | Synthetic 10 jenis vs real 33 jenis (UPPER_SNAKE_CASE) | `49_activity_distribution_detailed.csv` |
| 3 | Perbandingan kosakata | Kedua dataset + grep source code | Pemetaan semantik dua arah | 7 pasangan padanan semantik; aktivitas fiktif di synthetic; modul inti tak terwakili | `50_activity_vocabulary_comparison.csv` |
| 4 | Relasi aktivitas-objek | Kedua dataset | Inspeksi kolom objek per aktivitas | Real: target_tipe/target_id 100% terisi (7 tipe, 42 id); synthetic: object_count angka tanpa identitas | `51_activity_object_relationship.csv` |
| 5 | Path usage | Kedua dataset | Pencarian kolom path/filename | NOT_FOUND pada keduanya; path_file hanya di tabel berkas (3 baris unik) | `52_path_usage_audit.csv` |
| 6 | Perubahan path yang sama | Dataset + kode aplikasi | Analisis same-path change level log & aplikasi | HASH_NOT_AVAILABLE_IN_SYNTHETIC_DATASET; level aplikasi: hash isi file dianchored pada berkas.hash_sha256 | `53_same_path_change_audit.csv`, `56` |
| 7 | Mekanisme hashing | Source code backend | Penelusuran crypto/bcrypt/speakeasy | 5 mekanisme: chain SHA-256, fingerprint file SHA-256, bcrypt password, TOTP, skema verifikasi | `54_hash_mechanism_audit.csv` |
| 8 | Hash chain audit log | auditLogService.js | Telusuri pembentukan & verifikasi rantai | Chain lengkap: prev-link + rekomputasi; verifikasi on-demand via endpoint; tanpa auto-recovery | `55_hash_chain_flow.md` |
| 9 | Kasus "file diganti, path tetap" | berkasController.js | Analisis alur deteksi | Terdeteksi saat download/manual verify; warning POTENSI_ANOMALI_HASH_BERKAS + blokir akses 409 | `56_same_path_hash_detection_analysis.md` |
| 10 | Hubungan audit-log-hash | DB real 337 record + skema | Profil atribut integritas | hash_entri 337/337; hash_sebelumnya 336/337 (1 NULL kepala rantai); nilai hash FILE tidak masuk audit_log | `57_audit_log_hash_relationship.md`, `58` |
| 11 | Bukti integritas nyata | Tabel berkas & verifikasi_integritas_berkas | Query read-only | 3 berkas (semua ber-hash+path); status VALID 1 / BELUM_DIVERIFIKASI 2; riwayat verifikasi 1 (VALID); POTENSI_ANOMALI_HASH_BERKAS = 0 kejadian | `63_file_integrity_baseline.md` |
| 12 | Gap & kebutuhan atribut | Semua temuan | Identifikasi gap → rancangan requirements | 9 gap; rancangan atribut A–E dengan pemisahan fitur VAE vs ground truth | `59`, `60` |

Interpretasi selalu dipisahkan dari fakta; istilah integritas kriptografis tidak dicampur dengan deteksi anomali VAE.
