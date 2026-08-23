# 168 — Production Rollback & Safety Check (Tahap 12)

## Artefak produksi/dataset — TIDAK BERUBAH (hash terverifikasi `audit_n_stage12.py`)

| Artefak | SHA-256 (awal) | Status |
|---|---|---|
| `models/vae_model.pth` | baseline `vae_model_production` di t12_stats.json | UNCHANGED (git tracked, tidak muncul modified) |
| `models/deployment_config.json` | threshold 3.1496288776397705 | UNCHANGED |
| Stage 6 dataset | `5e9bf0d5…9e966` | UNCHANGED |
| Stage 8 features CSV | `ce4854fa…ef959` | UNCHANGED |
| Stage 9 encoded CSV | `63801485…46affc` | UNCHANGED |
| X_train_final.npy | `fe67e6c8…a59f` | UNCHANGED |
| X_validation_final.npy | `f6e5185b…2af3` | UNCHANGED |
| X_test_final.npy | `a2d02e16…3bc9` | UNCHANGED |
| PostgreSQL database | inference path tidak menyentuh DB; kredensial/DDL backend tidak dijalankan | UNTOUCHED |
| Generator dataset | tidak dimodifikasi | UNCHANGED |

## Rollback path

1. **Endpoint-level**: `/predict-stage11` adalah rute tambahan — rollback =
   hapus rute tersebut dari `app.py` (atau cukup berhenti memanggil endpoint);
   jalur produksi `/predict`, model lama, dan threshold lama tidak pernah
   diubah sehingga tidak ada yang perlu dipulihkan.
2. **Model-level**: model produksi tetap `models/vae_model.pth` +
   `deployment_config.json`; artefak kandidat hidup terpisah di
   `models/retrained/`. Cutover permanen (menjadikan Stage 11 sebagai
   produksi) sengaja TIDAK dilakukan di Tahap 12.
3. **Threshold**: tidak ada perubahan nilai berdasarkan hasil test —
   3.0499422550201416 hanya berlaku pada jalur kandidat.

## Perubahan source yang diperlukan wiring (satu-satunya)

- `ai-service/app.py`: +import `predict_stage11`, +rute `/predict-stage11`
  (additive, dapat dibalik dengan satu revert).
