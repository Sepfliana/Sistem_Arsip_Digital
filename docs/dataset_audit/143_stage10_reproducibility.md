# 143 — Reproducibility Tahap 10

- **Input**: `ai-service/dataset/encoded/audit_log_dataset_stage9_encoded_unscaled.csv`
  SHA-256 `853c362859db26c9a3c1912addf6825bc3f8404da9d9939bff02fad747258055`
- **Script**: `docs/dataset_audit/audit_k_stage10.py` (v1.0) — read-only terhadap
  seluruh sumber; artefak baru hanya di `ai-service/dataset/final/` + laporan.
- **Random seed**: 42 (`numpy.random.default_rng(42)`).
- **Split method**: group-based by session_id; 70/15/15 → 2.516/539/540 sesi;
  urutan grup acak deterministik.
- **Scaler**: StandardScaler fit TRAIN only (10.503 baris) —
  `dataset/final/scaler/final_train_scaler.pkl`; mean/scale/var di
  `final_dataset_metadata.json`.
- **Feature order**: user_id, activity, status, device, ip_address,
  duration_ms, object_count, hour, day_of_week.
- **Output + checksum (SHA-256)**:
  - X_train_final.npy `fe67e6c8bc1e5b4fdbb532a8b8691fba1c96068239689a19573c8625e182a59f`
  - X_validation_final.npy `f6e5185bf3a0486bcf7f28580a7354f9b64a1d95a6824775a92a933dbb2e2af3`
  - X_test_final.npy `a2d02e16fd76349709bd29bf43242f5d0929f6f847b522b34e7e20e409153bc9`
- **Execution timestamp**: 2026-08-23T15:39:38 (t10_stats.json).
- **Git commit**: b9857fc16b2d7c54a4517da0173e45cce6d243af.

Ulangi: `ai-service\.venv\Scripts\python.exe docs\dataset_audit\audit_k_stage10.py`
→ split, scaler, matriks, dan seluruh checksum identik (tanpa komponen stokastik
selain seed yang dikunci).
