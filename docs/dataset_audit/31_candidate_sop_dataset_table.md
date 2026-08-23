# 31 — Tabel Kandidat untuk Skripsi: Validasi Dataset vs SOP & Kondisi Operasional

| No | Aspek | Dasar | Kondisi Dataset Saat Ini | Hasil Validasi | Rekomendasi |
|---|---|---|---|---|---|
| 1 | Sumber dataset utama VAE | `preprocessing.py` → `generator/raw/audit_log_dataset.csv` | Synthetic 15.000 baris, seed 42, tahun 2025 | Teridentifikasi 100% sintetis; data real (337 baris) belum masuk training | Nyatakan eksplisit di metodologi bahwa baseline bersifat simulasi |
| 2 | Kamus aktivitas | `flows.py` (10 workflow) vs aksi backend (33 nilai) | 10 aktivitas Indonesia gaya UI | 3 aktivitas tanpa padanan nyata (Dashboard, Lihat Perkara, Kelola Kode Klasifikasi); modul Peminjaman/2FA/sarana tidak terwakili | Sinkronkan kamus dataset dengan aksi yang benar-benar terlog |
| 3 | Role → aktivitas | `flows.py`; JOIN roles pada log real | Pasangan role-aktivitas synthetic 100% sesuai workflow generator | Real: Admin mendominasi semua aksi (traffic uji); User didominasi peminjaman/2FA | Validasi ulang setelah data operasional bersih tersedia |
| 4 | Jam kerja | Instruksi penelitian 08.00–16.00; generator 07–17 | Synthetic: 08–15:59 = 77,55%; 07–07:59 = 9,36%; 16–16:59 = 9,73% | Parameter generator tidak selaras dengan klaim jam kerja; real hanya 40,65% di jam tersebut | Konfirmasi SOP jam kerja resmi (NEEDS_VERIFICATION) lalu samakan |
| 5 | Weekend | Generator acak | Synthetic weekend 27,99% (seragam); real 31,16% | Tidak ada pemodelan kalender sama sekali | Sertakan kalender kerja sebagai parameter dataset |
| 6 | Tanggal merah | Tidak ada sumber di repository | holiday_status UNKNOWN seluruh baris | Tidak dapat divalidasi; tidak direkonstruksi agar tidak mengarang | Sedeklarasi sumber kalender resmi sebelum dipakai |
| 7 | Atribut duration_ms | Backend tidak mengukur durasi (default 0) | Synthetic 1–106.760 ms bervariasi per aktivitas | Tanpa dukungan data nyata (real semuanya 0) | Perbaiki pengukuran di backend atau keluarkan dari fitur |
| 8 | Atribut object_count | Default backend = 1 | Synthetic 1–200 (anomali massal) | Tanpa dukungan data nyata (real semuanya 1) | Ikat ke fakta transaksi atau keluarkan |
| 9 | Atribut ip_address | Default backend 'unknown' | Synthetic 192.168.x + prefix publik | Real: 333/337 unknown; localhost sejati hanya 4 | Ekstrak IP klien asli di middleware |
| 10 | Atribut device | Default backend 'unknown' | Synthetic 5 device normal + 4 anomali | Real: unknown 333/337 + UA axios | Kirim User-Agent nyata dari klien resmi |
| 11 | Integritas hash berkas | `hash_sebelumnya/hash_entri` di tabel audit_log | Rantai SHA-256 utuh (0 invalid; 1 NULL awal rantai) | Ada di level DB; tidak diekspor ke dataset VAE mana pun | Putuskan posisi dimensi integritas dalam metodologi |
| 12 | Label normal/anomaly | Suntikan aturan generator (`anomaly.py`) | anomaly_type/risk_level ada di CSV, dibuang saat preprocessing | Label = definisi generator sendiri; evaluasi bersifat in-sample | Dokumentasikan batasan ini di metodologi evaluasi |

Semua sel merupakan hasil audit (Tahap 1–2); tidak ada angka yang diperkirakan.
