# 92 — Pemeriksaan Pemisahan Integritas vs VAE (RULE K/L)

## Penegasan

**HASH INTEGRITY DETECTION** dan **VAE ANOMALY DETECTION** adalah dua mekanisme yang TERPISAH dan tetap dipisahkan setelah Stage 6:

| Aspek | HASH INTEGRITY | VAE ANOMALY DETECTION |
|---|---|---|
| Dasar | Perbandingan SHA-256 isi file vs stored hash | Rekonstruksi 9 fitur perilaku vs threshold persentil-95 |
| Lokasi | `berkasController.js` (getBerkasFile, verifyBerkasIntegrity) + tabel verifikasi_integritas_berkas | ai-service (preprocessing → VAE → /predict) + laporan_anomali |
| Objek | Integritas fisik berkas | Pola perilaku pengguna |
| Input VAE | **TIDAK terlibat** | 9 fitur tanpa hash/path/file |

## Pemeriksaan Stage 6

1. Tidak ada hash baru dibuat; tidak ada mekanisme hash diubah (`git status` bersih pada backend/ai-service).
2. Kolom hash/path/file **tidak ditambahkan** ke dataset Stage 6 (column_count tetap 13).
3. Kontrak fitur bebas kontaminasi: regex forbidden-terms (hash/path/file/target) atas FEATURE_COLUMNS = **0 temuan** (`t6_stats.json.contaminations=[]`).
4. Aksi log `POTENSI_ANOMALI_HASH_BERKAS` tetap diklasifikasikan sebagai temuan integritas kriptografis — bukan keluaran model.

Status: **SEPARATION INTACT**.
