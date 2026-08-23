# 127 — Before/After Encoding & Scaling (Tahap 9)

| No | Feature Raw | Representasi Sebelum | Encoding/Transformasi | Scaling | Representasi Sesudah | Dimensi |
|---|---|---|---|---|---|---|
| 1 | user_id | string "1".."72" (72 unik) | passthrough → int64 | StandardScaler | float64 ter-skalasi (±2.24 s/d +1.67) | 1 |
| 2 | activity | 10 label teks UI | LabelEncoder alphabetical | StandardScaler | integer kode 0–9 lalu terskalasi (−1.75..+1.21) | 1 |
| 3 | status | Berhasil/Gagal | LabelEncoder: Berhasil=0, Gagal=1 | StandardScaler | kode biner ter-skalasi (−0.18..+5.69) | 1 |
| 4 | device | 9 variasi generator (Unknown Device=kelas sah #5) | LabelEncoder alphabetical | StandardScaler | integer 0–8 ter-skalasi (−1.52..+1.26) | 1 |
| 5 | ip_address | IPv4 string, 362 unik | `int(ipaddress.ip_address())` ordinal 32-bit [kontrak training] | StandardScaler | integer besar ter-skalasi; skew ekstrem (−11.38..+0.12) — mayoritas internal 192.168.* | 1 |
| 6 | duration_ms | float64 ms (1–106.760) | passthrough mentah (tanpa log1p) | StandardScaler | float64 ter-skalasi; outlier +33.8 σ | 1 |
| 7 | object_count | float64 count (1–200) | passthrough mentah | StandardScaler | ter-skalasi (+17.4 σ utk outlier massal) | 1 |
| 8 | hour | int 0–23 derivasi timestamp | passthrough (bukan cyclical) | StandardScaler | ter-skalasi (−3.52..+1.78) | 1 |
| 9 | day_of_week | int Senin=0..Minggu=6 | passthrough | StandardScaler | ter-skalasi (−1.54..+1.50) | 1 |

Total sesudah: 15.000 × **9** float64 (`audit_log_dataset_stage9_encoded.csv`).

Interpretasi utk skripsi: encoding mempertahankan kontrak sistem existing;
StandardScaler menyebabkan fitur IP sangat left-skewed karena dominasi blok
internal tunggal vs 300 IP publik yang jauh — karakteristik data, bukan bug
tahap ini; dicatat sebagai bahan evaluasi Tahap 10–11.
