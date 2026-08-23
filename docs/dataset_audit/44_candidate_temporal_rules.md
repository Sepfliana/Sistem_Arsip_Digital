# 44 — Rancangan Aturan Temporal (KANDIDAT — BELUM DITERAPKAN)

| No | Candidate Rule | Dasar | Evidence | Tujuan | Status |
|---|---|---|---|---|---|
| 1 | Jendela jam kerja analitis ditetapkan 08.00–16.00 (BEFORE <08:00; WORKING 08:00–15:59; AFTER >=16:00) untuk seluruh klasifikasi dataset | Acuan penelitian; dokumen SOP instansi belum ditemukan di repository | 33_hourly_distribution_detailed.csv; perbandingan dengan jendela generator 07–17 | Menyamakan definisi time_category antara audit, dataset, dan laporan skripsi | NEEDS_VERIFICATION |
| 2 | Klasifikasi hari tiga-kategori WORKDAY/WEEKEND/HOLIDAY dengan precedence HOLIDAY > WEEKEND > WORKDAY | Hasil audit + kalender resmi SKB 2025 | 39_temporal_matrix.csv | Matriks temporal yang deterministik dan dapat direproduksi | CANDIDATE |
| 3 | Daftar tanggal merah mengacu SKB 3 Menteri No.1017/2024, No.2/2024, No.2/2024 (17 libur nasional + 10 cuti bersama) | Sumber resmi pemerintah (setkab.go.id) | 37_holiday_calendar_audit.csv | Kalender HOLIDAY terverifikasi, tidak dikarang | SUPPORTED_BY_DATA |
| 4 | Cuti bersama diperlakukan setara libur nasional dalam klasifikasi HOLIDAY | SKB menetapkannya sebagai hari libur; keberlakuan khusus instansi Kejaksaan belum diverifikasi | 37_holiday_calendar_audit.csv baris "Cuti Bersama" | Konsistensi klasifikasi non-kerja | NEEDS_VERIFICATION |
| 5 | Aktivitas di luar jam kerja / weekend / tanggal merah TIDAK otomatis menjadi anomali; label anomali hanya dari kolom ground-truth dataset (`anomaly_type`) | Aturan ketat tahap ini + prinsip tidak memberi label berdasarkan waktu | 43_temporal_issue_analysis.csv (istilah characteristic/candidate issue) | Mencegah bias label temporal pada evaluasi VAE | SUPPORTED_BY_DATA |
| 6 | Record weekend/libur/luar jam kerja TIDAK dihapus pada tahap perbaikan apa pun | Aturan ketat penelitian | 36/39 CSV; total record harus tetap 15.000 sebelum keputusan eksplisit | Integritas dataset selama transformasi | CANDIDATE |
| 7 | Distribusi timestamp hasil regenerasi (bila dilakukan) mengikuti profil operasional terukur, bukan uniform-acak penuh | Temuan keseragaman distribusi | t3_stats.json hourly_counts; daily min 8 / max 90 | Dataset mencerminkan ritme kerja nyata | CANDIDATE |
| 8 | Timestamp antaraktivitas dalam satu sesi mempertahankan dependency waktu (gap realistis) | Temuan rantai sesi generator (median gap 100 s) | 40_generator_temporal_logic.md | Realisme urutan aktivitas dipertahankan saat regenerasi | CANDIDATE |
| 9 | Zona waktu timestamp dideklarasikan eksplisit (saat ini naive/tanpa tz; diasumsikan waktu lokal WIB) | Temuan format timestamp tanpa timezone | 04_schema_audit.csv Tahap 1 | Menghindari ambiguitas saat integrasi dengan log produksi | NEEDS_VERIFICATION |

Semua butir adalah REKOMENDASI. **Tidak ada aturan yang diterapkan** pada dataset/generator/model selama Tahap 3.
