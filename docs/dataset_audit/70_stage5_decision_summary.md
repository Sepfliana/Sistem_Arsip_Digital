# 70 — Ringkasan Keputusan Tahap 5

Sumber lengkap: `64_dataset_rule_decision_matrix.csv` (baris 1–40).

## 1. MUST_FIX
- Kosakata aktivitas synthetic (10) tidak selaras dengan aksi backend yang benar-benar terlog (33) — baris 11. Eksekusi = penyelarasan kamus saat regenerasi disetujui; interim pemetaan kanonik.

## 2. SHOULD_FIX
- Aktivitas fiktif tanpa padanan real: Dashboard, Lihat Perkara, Kelola Kode Klasifikasi (baris 12).
- Modul Peminjaman tidak terepresentasi (baris 13); keamanan akun 2FA/reset (14); lemari/rak & retensi (15); keluarga aksi integritas POTENSI_ANOMALI/VERIFIKASI (17).
- Fitur operasional tanpa dasar empiris real — device (21), ip_address (22), duration_ms (23), object_count (24): perbaikan WAJIB di sumber aplikasi (upstream), tanpa imputasi/fabrikasi.
- target_tipe/target_id absen dari synthetic sebagai atribut pendukung (29).

## 3. KEEP_AS_IS
- Rentang jam generator 07–17 (1); record <08:00 (3); >=16:00 (4); distribusi weekday seragam (5); weekend (6); aktivitas tanggal merah SKB (7); kombinasi non-kerja (8–9); label login_luar_jam (10); pemetaan semantik 7 pasangan (16); activity/status encoded (19–20); hour/day_of_week (25); fungsi synthetic sbg training baseline (30); NULL kepala rantai (37); distribusi atribut sintetis kaya (39).

## 4. DO_NOT_FIX (pelindung metodologi)
- Real 337 record TIDAK untuk training → external validation/behavioral/schema reference (31).
- Label anomaly_type/risk_level/is_anom dilarang masuk fitur (32).
- skor_anomali/tingkat_risiko post-event dilarang masuk fitur (33).

## 5. NEEDS_VERIFICATION
- user_id sbg fitur numerik mentah — risiko identity-leakage (18).
- Duplikat persis belum diaudit — scan wajib sebelum implementasi (38).
- Kalender libur 2026 utk data real (40).
- (Terhubung) SOP jam kerja 08:00–16:00 & cuti bersama instansi — CONFLICT_NEEDS_REVIEW baris 2.

## 6. NOT_RELEVANT_TO_VAE
- File hash SHA-256 (26); hash chain prev/current (27); path/nama_file (28) — tetap di integrity subsystem.

## CONFLICT_NEEDS_REVIEW
- Dokumen desain 10-fitur vs kode 9-fitur (34); klaim Stage5 localhost=329 vs faktual 'unknown' (35); perbedaan granularitas bucket jam antar-output audit (36). Semua sudah didokumentasikan dengan resolusi (kode/angka audit sbg acuan).

RULES APPROVED FOR STAGE 6
- A Timestamp: NO modification existing timestamps.
- B Working hours: analisis-only metadata.
- C Weekend: no deletion/relabel.
- D Holiday: no deletion/relabel; kalender SKB sbg metadata.
- E Activity: DOCUMENT_ONLY mapping artifact; rename/regenerasi DEFERRED_TO_GENERATOR_V2.
- F Role/activity: diperluas hanya via regenerasi (DEFERRED).
- G–J IP/Device/Duration/ObjectCount: DEFERRED_TO_APPLICATION_DATA_CAPTURE; no imputation.
- K Path/file & L Hash: excluded dari fitur VAE (protective).
- M Labels: excluded dari fitur (protective).
- N Duplicate: verification-only scan.
- O Missing values: no imputation (NULL rantai sah).
- P Synthetic/real separation: real tidak masuk training.
