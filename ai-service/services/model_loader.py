"""Compatibility loader for the only active final VAE artifact.

Historical loaders remain in ``model_loader_legacy_pre_final.py``.  No caller
in the active application may load ``models/vae_model.pth`` directly.
"""

from services.final_vae_pipeline import FinalVariationalAutoencoder, load_final_model


VariationalAutoencoder = FinalVariationalAutoencoder


def load_model() -> FinalVariationalAutoencoder:
    """Load ``models/final_vae/vae_model_final.pth`` in deterministic eval mode."""
    return load_final_model()
