import hashlib
import json
import pickle
import sys
from pathlib import Path
import torch
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from services.model_loader import VariationalAutoencoder

BACKUP_DIR = BASE_DIR / "backup_before_vae_retraining"

prod_files = [
    (BASE_DIR / "models" / "vae_model.pth", "vae_model.pth"),
    (BASE_DIR / "models" / "deployment_config.json", "deployment_config.json"),
    (BASE_DIR / "dataset" / "preprocessed" / "scaler.pkl", "scaler.pkl"),
    (BASE_DIR / "dataset" / "preprocessed" / "label_encoders.pkl", "label_encoders.pkl"),
    (BASE_DIR / "dataset" / "preprocessed" / "X_train.npy", "X_train.npy"),
]

def file_hash(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def validate_stage7():
    print("=== RUNNING VALIDATE_STAGE7 DYNAMIC DISK CHECKPOINT ASSERTIONS ===")
    
    # 1. SHA-256 Hash Verification against Production Backup
    for p, name in prod_files:
        h_prod = file_hash(p)
        h_bak = file_hash(BACKUP_DIR / name)
        assert h_prod == h_bak, f"[FAIL] Production artifact {name} was modified!"
    print("[PASS] Production SHA-256 integrity verified.")

    # 2. Production Config Threshold Assert
    cfg_file = BASE_DIR / "models" / "deployment_config.json"
    with open(cfg_file, "r") as f:
        cfg = json.load(f)
    prod_thresh = cfg["threshold"]
    assert abs(prod_thresh - 3.1496288776397705) < 1e-6, "[FAIL] Production threshold was modified!"
    print("[PASS] Production threshold remains 3.149629.")

    # 3. Stage 7 Artifacts Existence & Checkpoint Dynamic Load
    stage7_dir = BASE_DIR / "stage7"
    cand_model_path = BASE_DIR / "models" / "candidate" / "vae_model_candidate.pth"
    cand_scaler_path = BASE_DIR / "dataset" / "retraining" / "candidate_scaler.pkl"
    cand_encoders_path = BASE_DIR / "dataset" / "retraining" / "candidate_encoders.pkl"
    canon_file = BASE_DIR / "dataset" / "retraining" / "retraining_dataset_canonical.csv"

    assert (stage7_dir / "stage7_evaluation_report.md").exists(), "[FAIL] stage7_evaluation_report.md missing!"
    assert cand_model_path.exists(), "[FAIL] vae_model_candidate.pth missing!"
    
    cand_hash = file_hash(cand_model_path)
    old_backup_hash = file_hash(BASE_DIR / "backup_before_stage6_fix" / "vae_model_candidate.pth")
    assert cand_hash != old_backup_hash, f"[FAIL] Candidate checkpoint on disk is identical to old failed backup!"
    print(f"[PASS] Candidate checkpoint on disk verified (SHA-256: {cand_hash[:16]}...).")

    # 4. Direct Inference Verification from Disk Checkpoint
    model = VariationalAutoencoder()
    model.load_state_dict(torch.load(cand_model_path, map_location="cpu"))
    model.eval()

    import pandas as pd
    df_canon = pd.read_csv(canon_file)
    df_lh = df_canon[df_canon["source_type"] == "REAL_DB"]
    assert len(df_lh) == 329, f"Localhost row count mismatch: {len(df_lh)}"

    with open(cand_scaler_path, "rb") as f:
        scaler = pickle.load(f)
    with open(cand_encoders_path, "rb") as f:
        encoders = pickle.load(f)

    lh_encoded = []
    for idx, row in df_lh.iterrows():
        act_i = int(encoders["activity"].transform([row["activity"]])[0])
        stat_i = int(encoders["status"].transform([row["status"]])[0])
        dev_i = int(encoders["device"].transform([row["device"]])[0])
        ip_i = int(encoders["ip_address"].transform([row["ip_address"]])[0])
        lh_encoded.append([
            float(row["user_id"]), float(act_i), float(stat_i), float(dev_i), float(ip_i),
            float(row["duration_ms"]), float(row["object_count"]), float(row["hour"]), float(row["day_of_week"])
        ])

    X_lh_scaled = scaler.transform(np.array(lh_encoded, dtype=np.float32)).astype(np.float32)
    with torch.no_grad():
        t_lh = torch.from_numpy(X_lh_scaled).float()
        r_lh, _, _ = model(t_lh)
        lh_mse = torch.mean((t_lh - r_lh).pow(2), dim=1).numpy()

    lh_anom_count = int((lh_mse > 3.1496288776397705).sum())
    lh_mean_mse = float(np.mean(lh_mse))

    assert lh_anom_count == 0, f"[FAIL] Localhost direct inference failed: {lh_anom_count} false positives!"
    assert lh_mean_mse < 0.05, f"[FAIL] Localhost mean MSE too high: {lh_mean_mse}"

    print(f"[PASS] Direct Localhost Inference: {len(df_lh)-lh_anom_count}/{len(df_lh)} NORMAL (Mean MSE: {lh_mean_mse:.6f})")
    print("[PASS] Localhost FPR = 0.00%")
    print("[PASS] No production deployment performed.")

    print("\n============================================================")
    print("ALL STAGE 7 VALIDATION ASSERTIONS PASSED 100%!")
    print("============================================================")
    return 0

if __name__ == "__main__":
    sys.exit(validate_stage7())
