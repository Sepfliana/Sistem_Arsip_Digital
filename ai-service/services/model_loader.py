"""Loading utilities for the locked final PyTorch VAE artifact."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import torch
from torch import Tensor, nn


SERVICE_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = SERVICE_DIR / "models" / "vae_model.pth"
MODEL_CONFIG_PATH = SERVICE_DIR / "models" / "vae_config.json"


class VariationalAutoencoder(nn.Module):
    """Architecture of the final, already-trained 9-feature VAE."""

    def __init__(self) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(9, 64), nn.ReLU(), nn.Dropout(0.2), nn.Linear(64, 32), nn.ReLU()
        )
        self.mu = nn.Linear(32, 8)
        self.logvar = nn.Linear(32, 8)
        self.decoder = nn.Sequential(
            nn.Linear(8, 32), nn.ReLU(), nn.Linear(32, 64), nn.ReLU(), nn.Linear(64, 9)
        )

    def forward(self, inputs: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        encoded = self.encoder(inputs)
        mu = self.mu(encoded)
        logvar = self.logvar(encoded)
        latent = mu + torch.exp(0.5 * logvar) * torch.randn_like(mu)
        return self.decoder(latent), mu, logvar


@lru_cache(maxsize=1)
def load_model() -> VariationalAutoencoder:
    """Load the final VAE once in CPU evaluation mode."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model final tidak ditemukan: {MODEL_PATH}")
    if not MODEL_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Konfigurasi model final tidak ditemukan: {MODEL_CONFIG_PATH}")

    config = json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))
    if int(config.get("input_dimension", 0)) != 9:
        raise ValueError("vae_config.json tidak sesuai kontrak 9 feature.")

    checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
    state_dict = checkpoint.get("model_state_dict", checkpoint)
    model = VariationalAutoencoder()
    model.load_state_dict(state_dict)
    model.eval()
    return model
