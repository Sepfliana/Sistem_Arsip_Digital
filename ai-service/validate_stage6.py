import json
import pickle
import sys
from pathlib import Path
import torch
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from services.model_loader import VariationalAutoencoder
from utils.preprocessing_contract import process_record

def validate_stage6():
    print("=== RUNNING VALIDATE_STAGE6 ASSERTIONS ===")
    
    cand_model_path = BASE_DIR / "models" / "candidate" / "vae_model_candidate.pth"
    cand_scaler_path = BASE_DIR / "dataset" / "retraining" / "candidate_scaler.pkl"
    cand_encoders_path = BASE_DIR / "dataset" / "retraining" / "candidate_encoders.pkl"
    backup_dir = BASE_DIR / "backup_before_vae_retraining"

    assert cand_model_path.exists(), "Candidate model file missing!"
    assert cand_scaler_path.exists(), "Candidate scaler file missing!"
    assert cand_encoders_path.exists(), "Candidate encoders file missing!"
    assert backup_dir.exists(), "Production backup directory missing!"

    # Load Model
    model = VariationalAutoencoder()
    model.load_state_dict(torch.load(cand_model_path))
    model.eval()

    # Forward Pass Test
    dummy_in = torch.randn(10, 9)
    recon, mu, logvar = model(dummy_in)
    assert recon.shape == (10, 9)
    assert not torch.isnan(recon).any()
    assert not torch.isinf(recon).any()

    print("All Stage 6 Assertions PASSED successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(validate_stage6())
