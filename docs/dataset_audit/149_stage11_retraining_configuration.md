# 149 — Retraining Configuration (Tahap 11)

Baseline = konfigurasi existing (`train_vae_pytorch.py`), tidak ada perubahan
arsitektur/hyperparameter tanpa evidence.

| Parameter | Nilai | Sumber |
|---|---|---|
| input_dimension | 9 | existing |
| hidden layers | encoder [64,32]; decoder [32,64] | existing |
| latent_dimension | 8 (mu/logvar) | existing |
| activation / dropout | ReLU / 0.2 (encoder) | existing |
| loss | MSE + 1.0·\|KL − capacity\|; annealing target 0.5, warmup 60 epoch | existing |
| optimizer / lr | Adam / 0.001 | existing |
| batch_size | 30004 → full-batch pada 10.503 baris | existing |
| epochs | 100 | existing |
| early stopping | tidak ada di existing; TIDAK ditambah sebagai stopping — yang ditambah: monitoring val-loss per epoch + model selection best-val (keputusan terdokumentasi) | baru (metodologi) |
| checkpoint strategy | model terbaik disimpan via deepcopy state_dict best-val; produksi tidak disentuh | adaptasi |
| seed | python=numpy=torch=42; `torch.use_deterministic_algorithms(True)`; threads=4 | existing + deterministic flag |

## Data

- TRAIN: X_train_final.npy (10.503×9) — satu-satunya sumber gradien.
- VALIDATION: monitoring/model selection saja.
- TEST: tidak disentuh sampai evaluasi final.

## Output

`models/retrained/vae_model_stage11.pth`, `stage11_threshold.json`,
`stage11_model_metadata.json` — model/threshold/deployment config produksi
tidak di-overwrite.
