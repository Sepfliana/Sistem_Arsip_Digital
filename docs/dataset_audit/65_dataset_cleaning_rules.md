# 65 — Aturan Perbaikan Dataset (untuk Tahap 6 — BELUM DITERAPKAN)

Semua aturan bersumber dari `64_dataset_rule_decision_matrix.csv`. Aturan berstatus APPROVED hanya boleh dieksekusi di Tahap 6; yang NEEDS_VERIFICATION wajib diverifikasi dulu.

### RULE A — Timestamp
- **Rule**: Tidak ada modifikasi timestamp pada dataset existing (no shifting/re-basing).
- **Action**: NONE pada v1; regenerasi v2 boleh menetapkan timestamp baru sejak awal.
- **Evidence**: baris 1; 40_generator_temporal_logic.md. **Priority**: HIGH.
- **Expected effect**: integritas data latihan terjaga. **Risk**: jika dilanggar → data buatan ganda tanpa jejak.

### RULE B — Working hours
- **Rule**: 08:00–16:00 dipakai hanya sebagai lensa analisis pelaporan.
- **Action**: tidak mengubah record; konfirmasi SOP instansi sebelum aturan lanjutan.
- **Evidence**: baris 2–4. **Priority**: MEDIUM. **Expected effect**: konsistensi istilah skripsi. **Risk**: klaim SOP keliru bila dikonfirmasi asal.

### RULE C — Weekend
- **Rule**: weekend TIDAK dihapus, difilter, atau direlabel anomali.
- **Action**: NONE. **Evidence**: baris 5–6; aturan ketat Tahap 3/5. **Priority**: CRITICAL (protective).
- **Expected effect**: representasi kalender utuh. **Risk**: bila dihapus → bias distribusi hari.

### RULE D — Holiday
- **Rule**: tanggal merah TIDAK dihapus/direlabel; klasifikasi HOLIDAY synthetic memakai kalender SKB 2025 terverifikasi.
- **Action**: NONE pada data; referensi kalender disimpan sbg metadata analisis.
- **Evidence**: baris 7, 9, 40. **Priority**: CRITICAL (protective). **Expected effect**: audit reproducible. **Risk**: kalender 2026 real belum tersedia (NEEDS_VERIFICATION).

### RULE E — Activity vocabulary
- **Rule**: selaraskan kamus aktivitas generator dengan aksi backend yang benar-benar terlog saat regenerasi v2 disetujui; interim pertahankan pemetaan kanonik.
- **Action**: Stage 6 hanya boleh membuat artefak pemetaan/dokumen; perubahan kamus = bagian regenerasi.
- **Evidence**: baris 11–17. **Priority**: HIGH. **Expected effect**: kosakata latihan = operasional. **Risk**: regenerasi mengubah baseline → wajib bandingkan via 63/47.

### RULE F — Role/activity
- **Rule**: pasangan role→workflow generator dipertahankan dan diperluas konsisten dengan role baru aksi tambahan (Peminjaman=Admin/Arsiparis/User sesuai kode).
- **Evidence**: baris 13–15; flows.py. **Priority**: MEDIUM. **Expected effect**: cakupan modul lengkap. **Risk**: workflow baru butuh validasi ulang distribusi.

### RULE G — IP
- **Rule**: JANGAN imputasi/fabrikasi IP pada dataset existing; perbaikan hanya di sumber aplikasi (middleware ekstraksi IP asli) untuk data ke depan.
- **Evidence**: baris 22; 58 (333/337 'unknown'). **Priority**: HIGH. **Expected effect**: fitur ip_address punya dasar empiris di v2. **Risk**: tetap 'unknown' → fitur tetap tak informatif (dinyatakan eksplisit).

### RULE H — Device
- **Rule**: idem IP — kirim User-Agent nyata dari klien; tanpa imputasi.
- **Evidence**: baris 21. **Priority**: HIGH. **Risk**: idem.

### RULE I — Duration
- **Rule**: idem — ukur durasi nyata di middleware; tanpa sintesis angka pada data existing.
- **Evidence**: baris 23. **Priority**: HIGH. **Risk**: durasi 0 permanen membuat fitur mati di inference real.

### RULE J — Object count
- **Rule**: kaitkan jumlah_objek ke fakta transaksi di aplikasi; tanpa fabrikasi.
- **Evidence**: baris 24. **Priority**: MEDIUM. **Risk**: label peminjaman_massal/verifikasi_massal tetap tanpa konteks.

### RULE K — File/path
- **Rule**: path/file TIDAK menjadi fitur VAE; hanya atribut pendukung/integrity subsystem.
- **Evidence**: baris 28; 56 (pemisahan dua mekanisme). **Priority**: CRITICAL (protective). **Expected effect**: bebas leakage identitas objek. **Risk**: -.

### RULE L — Hash
- **Rule**: hash (chain & file) TIDAK masuk input VAE; tetap di integrity subsystem; pemisahan HASH INTEGRITY vs VAE ANOMALY dipertahankan.
- **Evidence**: baris 26–27; 54–57. **Priority**: CRITICAL (protective). **Risk**: mencampur mekanisme merusak validitas kedua subsistem.

### RULE M — Labels
- **Rule**: anomaly_type/risk_level/is_anom/skor_anomali/tingkat_risiko dilarang masuk fitur; hanya evaluasi/ground truth.
- **Evidence**: baris 32–33; preprocessing.py sudah membuangnya. **Priority**: CRITICAL (protective). **Risk**: target leakage.

### RULE N — Duplicate
- **Rule**: belum ada penghapusan duplikat (evidence kurang); scan dedup persis WAJIB dijalankan sebagai langkah verifikasi Tahap 6 sebelum transformasi apa pun; multi-event dalam satu session sah dan tidak dianggap duplikat.
- **Evidence**: baris 38. **Priority**: MEDIUM. **Risk**: dedup naif menghapus rantai sesi.

### RULE O — Missing values
- **Rule**: NULL hash_sebelumnya kepala rantai = struktur sah (jangan diisi); kolom lain synthetic 0% missing; real 'unknown'/0/1 adalah nilai sengaja dari aplikasi — diperlakukan sbg karakteristik, bukan missing.
- **Evidence**: baris 37; 05_quality_audit.csv. **Priority**: HIGH (protective). **Risk**: imputasi memalsukan rantai/karakteristik.

### RULE P — Synthetic/real separation
- **Rule**: synthetic tetap training v1; real 337 record HANYA external validation/behavioral reference/schema validation — dilarang digabung atau jadi training.
- **Evidence**: baris 30–31; 42; dominasi trafik uji. **Priority**: CRITICAL. **Expected effect**: metodologi bersih. **Risk**: penggabungan mencampur rezim data berbeda.

Ringkasan status: APPROVED untuk Stage 6 = A,B,C,D,E(interim),F,G-J(upstream only),K,L,M,O,P + N(sebagai verifikasi). Semua bersifat PROTECTIVE (tidak mengubah data existing) kecuali artefak dokumentasi/pemetaan.
