# 136 — Dataset Split (Tahap 10)

## Audit split existing

TIDAK ada split terdokumentasi pada pipeline existing: `preprocessing.py`
menghasilkan satu `X_train.npy` penuh; `train_vae_pytorch.py` memakai seluruh
matriks itu untuk training. Tidak ada validation/test split, seed split, atau
temporal split di source mana pun → keputusan metodologis BARU dibuat di sini,
reproducible, bukan klaim warisan.

## Keputusan

- **Metode**: group-based split by `session_id` (satu sesi tidak boleh menyeberang
  split — mencegah kebocoran konteks alur kerja multi-event).
- **Seed**: 42 (`numpy.random.default_rng(42)`), shuffle grup deterministik.
- **Proporsi**: 70% / 15% / 15% dari 3.595 sesi → 2.516 / 539 / 540 grup.
- **Stratified eksplisit**: TIDAK (group-based dipilih agar sesi utuh);
  distribusi label hasilnya tetap proporsional (~10% anomali tiap split).

## Hasil

| Split | Sesi | Baris | Proporsi baris |
|---|---|---|---|
| Train | 2.516 | 10.503 | 70,02% |
| Validation | 539 | 2.266 | 15,11% |
| Test | 540 | 2.231 | 14,87% |
| Total | 3.595 | 15.000 | 100% |

Verifikasi: grup disjoint PASS · setiap baris tepat satu split PASS ·
0 sesi menyeberang split PASS. Distribusi lengkap: `138`.
