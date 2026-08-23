# 30 — Rancangan Awal Aturan Dataset (REKOMENDASI — BELUM DITERAPKAN)

Semua butir di bawah adalah kandidat aturan untuk tahap perbaikan berikutnya. **Tidak ada yang dieksekusi pada tahap ini.** Setiap aturan menyebut dasar evidence-nya; yang tidak memiliki dasar internal diberi tanda NEEDS_VERIFICATION.

## R1. Sumber & kamus aktivitas
- Gunakan kamus aksi backend (`createAuditLog` di controllers) sebagai sumber tunggal jenis aktivitas, bukan kamus manual `flows.py`.
- Samakan kosakata status (SUCCESS/GAGAL vs Berhasil) sejak level log, atau dokumentasikan mapping kanonik sebagai bagian resmi pipeline.
- Dasar: 19_activity_sop_validation.csv (10 synthetic vs 33 aksi real).

## R2. Kelengkapan atribut sebelum masuk dataset
- IP address, device, durasi, dan jumlah objek hanya layak menjadi fitur jika aplikasi benar-benar mengisinya. Saat ini keempatnya default/unknown pada data real → wajib diperbaiki di sumber (middleware/backend) SEBELUM ekstraksi dataset.
- Dasar: 27_synthetic_real_comparison.csv; auditLogService.js default parameter.

## R3. Kalender kerja
- Definisikan kalender kerja resmi (hari kerja Senin–Jumat per instansi + daftar tanggal merah dengan sumber terdokumentasi). Saat ini tidak ada sumber kalender di project → NEEDS_VERIFICATION untuk daftar libur 2025/2026.
- Jam kerja 08.00–16.00 masih perlu dikonfirmasi terhadap SOP instansi (dokumen SOP tidak ditemukan di repository). Parameter generator saat ini 07–17.

## R4. Aturan pembentukan normal/anomaly (kandidat)
- Normal = kombinasi (role, activity) yang valid menurut workflow aplikasi + jam dalam jendela kerja resmi + hari kerja + atribut teknis konsisten (device/IP profil pengguna).
- Anomali tetap didefinisikan eksplisit dan berlabel, namun harus dibatasi pada kombinasi yang mungkin terjadi di sistem nyata (mis. anomali "peminjaman_massal" hanya relevan pada aksi peminjaman).
- Weekend/tanggal merah/di luar jam kerja TIDAK otomatis anomali — hanya menjadi konteks; anomali tetap ditentukan oleh pola perilaku.
- Dasar: 18_generator_behavior_analysis.md (anomali saat ini disuntik tanpa memandang jenis aktivitas).

## R5. Proporsi & skala
- Pertahankan kontrol rasio normal/anomali (mis. 90/10) tetapi turunkan dari distribusi real ketika data operasional cukup; tambahkan aktivitas modul yang hilang (Peminjaman, 2FA, sarana).
- Dasar: 29_dataset_gap_analysis.csv.

## R6. Reproducibility
- Setiap regenerasi dataset wajib mencatat: versi generator, seed, snapshot user/DB sumber, tanggal, dan hash file keluaran (dataset saat ini baru tercatat di git, belum ada manifest).
- Dasar: praktik repo saat ini (seed 42 ada, manifest tidak ada).

## R7. Pemisahan jalur
- Dataset training, validation, test dipisah eksplisit (saat ini seluruh 15.000 baris dipakai training tanpa split; folder processed kosong).
- Threshold dihitung dari data unseen, bukan persentil atas data training itu sendiri.
- Dasar: 03_actual_vae_data_flow.md.

> Status: SEMUA BUTIR DI ATAS BELUM DITERAPKAN. Tidak ada dataset/generator/model yang diubah pada tahap ini.
