# 126 — Feature Order Final Setelah Encoding (Tahap 9)

## Prinsip

LabelEncoder/IP-integer/passthrough adalah transformasi satu-kolom → **tidak ada
perluasan dimensi**; urutan final = FEATURE_COLUMNS kontrak (`preprocessing.py:24-34`).

| Posisi | raw feature (Stage 8) | encoded feature(s) | nilai akhir |
|---|---|---|---|
| 1 | user_id | passthrough int64 | ordinal numerik |
| 2 | activity | LabelEncoder | integer 0–9 |
| 3 | status | LabelEncoder | integer 0–1 |
| 4 | device | LabelEncoder | integer 0–8 |
| 5 | ip_address | ip_to_integer | integer 32-bit |
| 6 | duration_ms | passthrough float64 | ms mentah (pre-scale) |
| 7 | object_count | passthrough float64 | count mentah (pre-scale) |
| 8 | hour | passthrough | 0–23 (teramati 0–17) |
| 9 | day_of_week | passthrough | 0–6 |

Setelah StandardScaler seluruh kolom menjadi float64 ter-skalasi pada posisi yang sama.
Dimensi final intermediate: **15.000 × 9** — identik dengan input shape model aktif `(n, 9)`.

Catatan untuk Tahap 10: bila keputusan di kemudian hari memakai one-hot
(activity/device/ip_category), dimensi akan melebar dan kontrak model (n,9)
harus diubah bersamaan — saat itu bukan cakupan Tahap 9.
