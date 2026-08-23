# 124 — Encoding Contract (Tahap 9)

Metode mengikuti pipeline TRAINING existing (`preprocessing.py`) — bukan asumsi umum.

| feature | data type | semantic type | encoding method | output representation | output dim | reason | training/inference compatibility |
|---|---|---|---|---|---|---|---|
| user_id | int64 | categorical identifier | passthrough integer (existing) | ordinal numerik | 1 | kedua sisi existing memperlakukan numerik; mengubah = redesign model | WARNING (risiko ordinal, dipertahankan) |
| activity | string | nominal | LabelEncoder (alphabetical) | integer 0–9 | 1 | ENCODER_COLUMNS training | WARNING vocab vs inference kanonik |
| status | string | nominal biner | LabelEncoder | Berhasil=0, Gagal=1 | 1 | ENCODER_COLUMNS training | PASS (nama kelas sama) |
| device | string | nominal | LabelEncoder | integer 0–8; Unknown Device=5 eksplisit | 1 | ENCODER_COLUMNS training | WARNING (inference pakai 7 kelas kanonik) |
| ip_address | IPv4 string | konteks jaringan | `int(ipaddress.ip_address())` | integer 32-bit ordinal | 1 | kontrak training existing (`ip_to_integer`) | BLOCKER parity (inference kirim 0 konstan) |
| duration_ms | float64 | continuous behavioral | passthrough mentah | ms mentah → StandardScaler | 1 | training tanpa log1p | WARNING (inference log1p) |
| object_count | float64 | count behavioral | passthrough mentah | count mentah → StandardScaler | 1 | idem | WARNING (inference log1p) |
| hour | int 0–23 | siklikal kalender | passthrough (bukan cyclical — tanpa evidence di kode) | integer jam → StandardScaler | 1 | tidak ada cyclical encoding di source mana pun | WARNING (timezone inference) |
| day_of_week | int 0–6 | ordinal kalender Senin=0…Minggu=6 | passthrough | integer hari → StandardScaler | 1 | convention pandas `dt.dayofweek` | PASS convention; WARNING timezone |

Total dimensi tetap **9** (semua encoder satu-kolom; tidak ada one-hot).

## Mapping eksplisit hasil fit (deterministic, alphabetical)

- activity: Cari Berkas=0, Dashboard=1, Input Berkas=2, Kelola Kode Klasifikasi=3,
  Kelola User=4, Lihat Berkas=5, Lihat Perkara=6, Login=7, Logout=8, Verifikasi=9
- status: Berhasil=0, Gagal=1
- device: Android=0, Laptop Windows=1, Linux=2, MacOS=3, PC Windows=4,
  Unknown Device=5, Virtual Machine=6, Windows=7, iPhone=8

Unknown policy: dataset tidak memiliki nilai unknown baru; "Unknown Device" adalah
kategori generator yang sah dan tetap di-encode sebagai kelas tersendiri (5).
