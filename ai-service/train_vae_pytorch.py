"""Train the specified PyTorch Variational Autoencoder from preprocessed data."""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

import numpy as np
import torch
from torch import Tensor, nn
from torch.nn import functional as functional
from torch.utils.data import DataLoader, TensorDataset


SERVICE_DIR = Path(__file__).resolve().parent
DATA_PATH = SERVICE_DIR / "dataset" / "preprocessed" / "X_train.npy"
OUTPUT_DIR = SERVICE_DIR / "models"
MODEL_PATH = OUTPUT_DIR / "vae_model.pth"
CONFIG_PATH = OUTPUT_DIR / "vae_config.json"
HISTORY_PATH = OUTPUT_DIR / "training_history.json"
CHECKPOINT_PATH = OUTPUT_DIR / "checkpoint.pth"

CONFIG = {
    "input_dimension": 9,
    "latent_dimension": 8,
    "hidden_layers": {"encoder": [64, 32], "decoder": [32, 64]},
    "activation": "ReLU",
    "dropout": 0.2,
    "optimizer": "Adam",
    "learning_rate": 0.001,
    "epochs": 100,
    "batch_size": 30004,
    "training_strategy": "KL capacity annealing",
    "capacity_target": 0.5,
    "capacity_warmup_epochs": 60,
    "capacity_loss_weight": 1.0,
}


class VariationalAutoencoder(nn.Module):
    """VAE with the required 9-64-32-8 and 8-32-64-9 architecture."""

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
        standard_deviation = torch.exp(0.5 * logvar)
        latent = mu + standard_deviation * torch.randn_like(standard_deviation)
        return self.decoder(latent), mu, logvar


def validate_data(values: np.ndarray) -> None:
    if values.ndim != 2 or values.shape[1] != CONFIG["input_dimension"]:
        raise ValueError(
            f"Expected X_train with shape (n, {CONFIG['input_dimension']}), got {values.shape}."
        )
    if len(values) == 0:
        raise ValueError("X_train.npy is empty.")
    if not np.issubdtype(values.dtype, np.number) or not np.isfinite(values).all():
        raise ValueError("X_train.npy must contain only finite numeric values.")


def kl_capacity(epoch: int) -> float:
    """Linearly increase the allowed information capacity of the latent code."""
    progress = min(epoch / CONFIG["capacity_warmup_epochs"], 1.0)
    return float(CONFIG["capacity_target"] * progress)


def save_checkpoint(
    model: VariationalAutoencoder,
    optimizer: torch.optim.Optimizer,
    current_epoch: int,
    training_history: list[dict[str, float | int]],
    best_loss: float,
) -> None:
    """Atomically persist all state needed to resume at the next epoch."""
    checkpoint = {
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "current_epoch": current_epoch,
        "training_history": training_history,
        "best_loss": best_loss,
        "python_random_state": random.getstate(),
        "numpy_random_state": np.random.get_state(),
        "torch_rng_state": torch.random.get_rng_state(),
    }
    temporary_path = CHECKPOINT_PATH.with_suffix(".tmp")
    torch.save(checkpoint, temporary_path)
    os.replace(temporary_path, CHECKPOINT_PATH)


def resume_if_available(
    model: VariationalAutoencoder,
    optimizer: torch.optim.Optimizer,
) -> tuple[int, list[dict[str, float | int]], float]:
    """Restore the most recently completed epoch when a checkpoint exists."""
    if not CHECKPOINT_PATH.exists():
        return 1, [], float("inf")

    checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=False)
    required_keys = {
        "model_state_dict",
        "optimizer_state_dict",
        "current_epoch",
        "training_history",
        "best_loss",
    }
    missing_keys = required_keys.difference(checkpoint)
    if missing_keys:
        raise ValueError(f"Checkpoint tidak valid; key hilang: {sorted(missing_keys)}")

    model.load_state_dict(checkpoint["model_state_dict"])
    optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
    if "python_random_state" in checkpoint:
        random.setstate(checkpoint["python_random_state"])
    if "numpy_random_state" in checkpoint:
        np.random.set_state(checkpoint["numpy_random_state"])
    if "torch_rng_state" in checkpoint:
        torch.random.set_rng_state(checkpoint["torch_rng_state"])
    current_epoch = int(checkpoint["current_epoch"])
    history = list(checkpoint["training_history"])
    if len(history) != current_epoch:
        raise ValueError("Checkpoint tidak valid; panjang training_history tidak sesuai current_epoch.")

    print(f"Resume training dari epoch {current_epoch + 1}.")
    return current_epoch + 1, history, float(checkpoint["best_loss"])


def main() -> None:
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    # Use a bounded thread pool for the full-batch dense matrix operations.
    torch.set_num_threads(4)

    values = np.load(DATA_PATH)
    validate_data(values)
    dataset = TensorDataset(torch.from_numpy(values.astype(np.float32, copy=False)))
    loader = DataLoader(dataset, batch_size=CONFIG["batch_size"], shuffle=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model = VariationalAutoencoder()
    optimizer = torch.optim.Adam(model.parameters(), lr=CONFIG["learning_rate"])
    start_epoch, history, best_loss = resume_if_available(model, optimizer)

    model.train()
    for epoch in range(start_epoch, CONFIG["epochs"] + 1):
        total_loss = reconstruction_total = kl_total = 0.0
        samples = 0
        target_capacity = kl_capacity(epoch)
        for (batch,) in loader:
            optimizer.zero_grad()
            reconstruction, mu, logvar = model(batch)
            reconstruction_loss = functional.mse_loss(reconstruction, batch, reduction="mean")
            kl_loss = -0.5 * torch.mean(
                torch.sum(1 + logvar - mu.pow(2) - logvar.exp(), dim=1)
            )
            # Encourage a growing nonzero latent-information capacity.
            loss = reconstruction_loss + CONFIG["capacity_loss_weight"] * torch.abs(
                kl_loss - target_capacity
            )
            loss.backward()
            optimizer.step()

            size = batch.size(0)
            samples += size
            total_loss += loss.item() * size
            reconstruction_total += reconstruction_loss.item() * size
            kl_total += kl_loss.item() * size

        epoch_history = {
            "epoch": epoch,
            "train_loss": total_loss / samples,
            "reconstruction_loss": reconstruction_total / samples,
            "kl_loss": kl_total / samples,
            "kl_capacity": target_capacity,
        }
        history.append(epoch_history)
        best_loss = min(best_loss, float(epoch_history["train_loss"]))
        save_checkpoint(model, optimizer, epoch, history, best_loss)

    if not history:
        raise RuntimeError("Training history kosong; tidak ada epoch yang dapat disimpan.")
    torch.save({"model_state_dict": model.state_dict(), "config": CONFIG}, MODEL_PATH)
    CONFIG_PATH.write_text(json.dumps(CONFIG, indent=2), encoding="utf-8")
    HISTORY_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    final = history[-1]
    print(f"Jumlah data training: {len(dataset)}")
    print(f"Shape dataset: {tuple(values.shape)}")
    print(f"Epoch terakhir: {final['epoch']}")
    print(f"Final Loss: {final['train_loss']:.6f}")
    print(f"Final Reconstruction Loss: {final['reconstruction_loss']:.6f}")
    print(f"Final KL Loss: {final['kl_loss']:.6f}")


if __name__ == "__main__":
    main()
