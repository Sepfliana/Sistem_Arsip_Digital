# 163 — Audit Deployment Contract (Tahap 12)

## Jalur inference existing (produksi)

| Komponen | File | Perilaku |
|---|---|---|
| Endpoint | `app.py` `/predict` | PredictRequest → `services.inference.predict` |
| Model loader | `services/model_loader.py` | `models/vae_model.pth` + `vae_config.json` (input 9) |
| Threshold | `services/inference.py` | `deployment_config.json` = 3.14963 (sekali dibuat P95 train lama) |
| Preprocessing | `utils/preprocessing.py` + `preprocessing_contract.py` | kanonik 12/7 vocab; IP kategori → **ip_encoded=0 konstan** (kunci encoder tak ada); log1p durasi/objek; naive dianggap UTC→WIB |

## Kontrak model Tahap 11 (target deployment)

9 fitur urutan tetap user_id…day_of_week · arsitektur 9-64-32-8/8-32-64-9 ·
threshold kandidat 3.0499422550201416 · scaler final_train_scaler.pkl
(fit TRAIN-only 10.503) · encoder artefak Stage 9 (vocab 10/2/9).

## Gap produksi vs training (dari Tahap 9–11)

1. IP: integer training vs 0 konstan inference — **BLOCKER utama**.
2. Vocabulary activity/device berbeda.
3. duration/object_count log1p vs raw.
4. Timezone handling berbeda.
5. Scaler berbeda.

Keputusan arsitektur solusi: jalur kandidat TERPISAH (`services/inference_stage11.py`)
yang mereplikasi preprocessing training-side secara eksak — jalur produksi lama
tidak disentuh sehingga regression risk minimal dan perbandingan tetap bisa dilakukan.
