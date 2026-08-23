# 91 — Status Fitur Operasional (RULE G/H/I/J)

Kondisi `ip_address`, `device`, `duration_ms`, `object_count` dan alasan tidak diubah pada Stage 6:

| Fitur | Synthetic (Stage 6 = tetap) | Real | Keputusan |
|---|---|---|---|
| ip_address | 192.168.x.x + prefix publik (variatif, dipertahankan) | 'unknown' 333/337; localhost sejati 4 | **DEFERRED_TO_APPLICATION_DATA_CAPTURE** — ekstraksi IP klien asli harus diperbaiki di middleware aplikasi |
| device | 5 normal + 4 anomali sintetis | 'unknown' 333/337 + UA axios | idem — kirim User-Agent nyata dr klien resmi |
| duration_ms | 1–106.760 ms bervariasi | semua 0 (default parameter) | idem — ukur durasi nyata di middleware |
| object_count | 1–200 (massal utk anomali) | semua 1 (default) | idem — ikat ke fakta transaksi |

## Alasan tidak diubah pada Stage 6

1. **Larangan fabrikasi**: mengarang/mengimputasi nilai palsu dilarang keras (aturan keras Tahap 6; matriks baris 21–24).
2. **Sumber masalah di upstream**: data real buruk karena aplikasi mengirim default ('unknown'/0/1), bukan karena dataset salah merekamnya — memperbaiki dataset tanpa memperbaiki capture hanya menyembunyikan masalah.
3. **Fitur tetap dalam kontrak VAE**: kelengkapan real belum cukup untuk membuang fitur; penghapusan fitur hanya karena data real kosong tidak evidence-based (matriks baris 21–24, SHOULD_FIX upstream).
4. **Dataset synthetic sehat pada atribut ini** — variasinya justru utilitas latihan (baris 39, KEEP_AS_IS).

Status: **NO IMPUTATION — UPSTREAM DEFERRED**.
