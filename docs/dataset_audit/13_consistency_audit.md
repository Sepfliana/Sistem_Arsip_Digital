# 13 — Audit Konsistensi (Kontradiksi Dokumentasi vs Source Code vs Dataset)

Tidak ada kontradiksi yang diperbaiki pada tahap ini. Semua butir adalah temuan.

| # | Aspek | Dokumentasi / Artefak Lama | Source Code Aktual | Dataset Aktual | Status |
|---|---|---|---|---|---|
| 1 | Jumlah fitur VAE | `docs/VAE_ARCHITECTURE.md` menyatakan **10 fitur** (role, action, module, status, device, ip_address, duration_ms, object_count, hour, day_of_week) | `preprocessing.py:24-34`, `preprocessing_contract.py:59-69`, `train_vae_pytorch.py:26` → **9 fitur** (user_id menggantikan role+module; tidak ada kolom action/module) | X_train.npy = (15000, 9); metadata JSON = 9 | **KONTRADIKSI** — dokumen desain kedaluwarsa |
| 2 | Fitur `user_id` dalam VAE | `docs/VAE_ARCHITECTURE.md`: user_id sengaja TIDAK dijadikan input ("risiko model menghafal identitas") | `preprocessing.py:25` menjadikan `user_id` fitur #1; kontrak inference juga memakai user_id | user_id = 72 nilai unik di synthetic | **KONTRADIKSI** |
| 3 | Sumber data training | Stage 5 report: "dataset kandidat siap retraining (gabungan real+synthetic)" | `train_vae_pytorch.py:18` hanya membaca `dataset/preprocessed/X_train.npy`; tidak ada skrip yang membaca artefak `retraining/` | X_train.npy dibuat 2026-07-27 murni dari synthetic; candidate .npy (2026-08-16) tak terpakai | **KETIDAKSESUAIAN** — retraining tidak pernah dilakukan |
| 4 | Real PostgreSQL = 329 baris | Stage 5 report: 329 | query ekstraksi lama memang 329 (15000+329=15329 konsisten) | COUNT(*) saat audit ini = **337** (data tumbuh) | **BENAR SAAT ITU, TIDAK LAGI** — klaim bersifat snapshot |
| 5 | Localhost = 329 baris | Stage 5 report: "329 baris Localhost" | `preprocessing_contract.map_ip_category` memetakan `'unknown'` → "Localhost / Loopback" | DB live: 333/337 IP = `'unknown'`; localhost sejati (`::1`, `::ffff:127.0.0.1`) hanya 4; canonical CSV mencatat 329 "Localhost / Loopback" karena termasuk 'unknown' | **MENYESATKAN** — mayoritas "localhost" adalah IP kosong/unknown |
| 6 | Kosakata aktivitas/status | docs arsitektur menyebut kolom `action`, `module`, `status` audit log | backend menulis aksi UPPER_SNAKE_CASE (`LOGIN_SUCCESS`, `CREATE_BERKAS`) tanpa kolom module | synthetic memakai kamus berbeda (`Login`, `Lihat Perkara`, status `Berhasil/Gagal` vs produksi `SUCCESS/VALID`) | **GAP SKEMA** — dijembatani mapping kanonik saat inference saja |
| 7 | Preprocessing training vs inference | — | training: IP integer + numerik mentah + jam lokal file; inference: kategori IP→encoder(=0), log1p, jam naive dianggap UTC→WIB | — | **INKONSISTENSI JALUR** (lihat 03_actual_vae_data_flow.md) |
| 8 | Threshold | — | persentil-95 atas error TRAINING (`inference.py:37-46`) | dihitung dari data yang sama persis dengan training → bukan error data unseen | **CATATAN METODOLOGI** |
| 9 | Model aktif | `config.py` default `MODEL_PATH=model/vae_model.keras` (legacy Keras); `evaluate.py` masih impor keras/train legacy | runtime PyTorch: `models/vae_model.pth` via `services/model_loader.py` | dua generasi artefak model ada bersamaan (`model/` legacy vs `models/` aktif) | **DOKUMEN/KONFIG LAMA BERTABRAKAN** dengan implementasi |
| 10 | Jam kerja synthetic | generator `WORK_START=7, WORK_END=17` | — | distribusi jam 07–16 rapat (~9-10%/jam), 17 hanya 0,35%, 18–23 nihil, 00–06 ±450 (label login_luar_jam) | KONSISTEN dgn kode generator; dicatat untuk analisis SOP tahap berikutnya |
| 11 | Kalender/tanggal merah | tidak ada daftar hari libur di repository | tidak ada logika kalender di kode | semua tanggal 2025 ada aktivitas; weekend 4.198 event (28%) — synthetic acak, tidak mengenal hari libur | **BELUM DAPAT DIPASTIKAN** untuk data real |
| 12 | Atribut file/path/hash pada dataset | skripsi konteks: integritas berkas via hash chaining | rantai hash hanya di tabel `audit_log` DB (`schema.sql:138-139`); tidak diekspor ke dataset manapun | ketiga CSV: TIDAK ADA atribut file/path/hash | **TERIDENTIFIKASI** — hash chain belum masuk ruang lingkup dataset VAE |

## Ringkasan Status

- CONFIRMED: jumlah record synthetic (15.000), combined (15.329), 9 fitur, duplicate combined 0, label bukan fitur canonical.
- NOT_CONFIRMED / MENYESATKAN: klaim "329 localhost" (ternyata mayoritas IP unknown), klaim implisit bahwa gabungan sudah/will dipakai training.
- Konfigurasi & model TIDAK diubah oleh Stage 5 (mtime `vae_model.pth` 28-07-2026 < `X_train_candidate.npy` 16-08-2026; tidak ada pembaca artefak kandidat).
