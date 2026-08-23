# -*- coding: utf-8 -*-
"""TAHAP 11 - Retraining & evaluasi VAE pada FINAL dataset.

Deterministik (seed 42). Tidak menyentuh model/threshold produksi.
Artefak baru: ai-service/models/retrained/ + laporan docs/dataset_audit/.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as functional
from torch.utils.data import DataLoader, TensorDataset

REPO = Path(__file__).resolve().parents[2]
SVC = REPO / "ai-service"
FINAL = SVC / "dataset" / "final"
MODELS = SVC / "models"
RT = MODELS / "retrained"
OUT = Path(__file__).resolve().parent

SEED = 42
CONFIG = {
    "input_dimension": 9, "latent_dimension": 8,
    "hidden_layers": {"encoder": [64, 32], "decoder": [32, 64]},
    "activation": "ReLU", "dropout": 0.2, "optimizer": "Adam",
    "learning_rate": 0.001, "epochs": 100, "batch_size": 30004,
    "training_strategy": "KL capacity annealing",
    "capacity_target": 0.5, "capacity_warmup_epochs": 60,
    "capacity_loss_weight": 1.0,
}
FEATURES = ["user_id", "activity", "status", "device", "ip_address",
            "duration_ms", "object_count", "hour", "day_of_week"]
EXPECT = {"train": (10503, 9), "validation": (2266, 9), "test": (2231, 9)}


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


started = datetime.now().isoformat()
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
try:
    torch.use_deterministic_algorithms(True)
except Exception:
    pass
torch.set_num_threads(4)

data, ids = {}, {}
for s in EXPECT:
    arr = np.load(FINAL / f"X_{s}_final.npy")
    data[s] = arr
    ids[s] = pd.read_csv(FINAL / f"{s}_metadata.csv", encoding="utf-8")["row_id"].to_numpy()
input_ok = all(data[s].shape == EXPECT[s] and data[s].dtype == np.float32
               and not np.isnan(data[s]).any() and not np.isinf(data[s]).any()
               for s in EXPECT)
print("input_ok:", input_ok, {s: data[s].shape for s in EXPECT})

class VariationalAutoencoder(nn.Module):
    """Arsitektur identik model produksi (9-64-32-8 / 8-32-64-9)."""

    def __init__(self) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(9, 64), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(64, 32), nn.ReLU())
        self.mu = nn.Linear(32, 8)
        self.logvar = nn.Linear(32, 8)
        self.decoder = nn.Sequential(
            nn.Linear(8, 32), nn.ReLU(), nn.Linear(32, 64),
            nn.ReLU(), nn.Linear(64, 9))

    def forward(self, inputs):
        encoded = self.encoder(inputs)
        mu = self.mu(encoded)
        logvar = self.logvar(encoded)
        std = torch.exp(0.5 * logvar)
        latent = mu + std * torch.randn_like(std)
        return self.decoder(latent), mu, logvar


def kl_capacity(epoch: int) -> float:
    progress = min(epoch / CONFIG["capacity_warmup_epochs"], 1.0)
    return float(CONFIG["capacity_target"] * progress)


def epoch_losses(model, values: np.ndarray, epoch: int):
    """Full-batch loss komponen (eval mode, no grad)."""
    model.eval()
    with torch.no_grad():
        batch = torch.from_numpy(values.astype(np.float32, copy=False))
        recon, mu, logvar = model(batch)
        r = functional.mse_loss(recon, batch, reduction="mean")
        kl = -0.5 * torch.mean(torch.sum(1 + logvar - mu.pow(2) - logvar.exp(), dim=1))
        cap = kl_capacity(epoch)
        total = r + CONFIG["capacity_loss_weight"] * torch.abs(kl - cap)
    return float(total), float(r), float(kl)


model = VariationalAutoencoder()
optimizer = torch.optim.Adam(model.parameters(), lr=CONFIG["learning_rate"])
g = torch.Generator().manual_seed(SEED)
loader = DataLoader(TensorDataset(torch.from_numpy(data["train"])),
                    batch_size=CONFIG["batch_size"], shuffle=True, generator=g)

history, best = [], {"val_total": float("inf"), "epoch": 0, "state": None}
for epoch in range(1, CONFIG["epochs"] + 1):
    model.train()
    tot = rec_t = kl_t = n = 0.0
    for (batch,) in loader:
        optimizer.zero_grad()
        recon, mu, logvar = model(batch)
        r = functional.mse_loss(recon, batch, reduction="mean")
        kl = -0.5 * torch.mean(torch.sum(1 + logvar - mu.pow(2) - logvar.exp(), dim=1))
        loss = r + CONFIG["capacity_loss_weight"] * torch.abs(kl - kl_capacity(epoch))
        loss.backward()
        optimizer.step()
        sz = batch.size(0)
        tot += loss.item() * sz; rec_t += r.item() * sz; kl_t += kl.item() * sz; n += sz
    vt, vr, vk = epoch_losses(model, data["validation"], epoch)
    history.append({"epoch": epoch,
                    "train_loss": tot / n, "train_recon": rec_t / n, "train_kl": kl_t / n,
                    "val_loss": vt, "val_recon": vr, "val_kl": vk,
                    "kl_capacity": kl_capacity(epoch)})
    if vt < best["val_total"]:
        import copy
        best = {"val_total": vt, "epoch": epoch,
                "state": copy.deepcopy(model.state_dict())}
print("best_epoch:", best["epoch"], "best_val_loss:", round(best["val_total"], 6))

# ---------------- artifacts ------------------------------------------------
RT.mkdir(parents=True, exist_ok=True)
model.load_state_dict(best["state"])
model.eval()
torch.save({"model_state_dict": best["state"], "config": CONFIG,
            "best_epoch": best["epoch"], "seed": SEED},
           RT / "vae_model_stage11.pth")

with (OUT / "150_stage11_training_history.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(history[0].keys()))
    w.writeheader()
    w.writerows(history)


def recon_errors(values: np.ndarray) -> np.ndarray:
    out = []
    with torch.no_grad():
        for i in range(0, len(values), 4096):
            b = torch.from_numpy(values[i:i + 4096])
            r, _, _ = model(b)
            out.append(torch.mean((b - r).pow(2), dim=1).cpu().numpy())
    return np.concatenate(out)


err = {s: recon_errors(data[s]) for s in EXPECT}
threshold = float(np.percentile(err["train"], 95))
val_threshold_ref = float(np.percentile(err["validation"], 95))
(RT / "stage11_threshold.json").write_text(json.dumps({
    "method": "percentile-95 of TRAIN reconstruction errors (metodologi existing dihitung ulang)",
    "threshold": threshold,
    "validation_p95_reference_not_used_for_selection": val_threshold_ref,
    "test_used": False}, indent=2), encoding="utf-8")

rows153 = []
def stat_block(split, vals):
    qs = np.percentile(vals, [1, 5, 25, 50, 75, 90, 95, 99])
    rows153.append([split, "ALL", len(vals), round(float(vals.min()), 6),
                    round(float(vals.max()), 6), round(float(vals.mean()), 6),
                    round(float(np.median(vals)), 6), round(float(vals.std()), 6)] +
                   [round(float(q), 6) for q in qs])

lab = {s: pd.read_csv(FINAL / f"{s}_metadata.csv", encoding="utf-8") for s in EXPECT}
for s in EXPECT:
    stat_block(s, err[s])
    for grp in ("Normal", "anomaly"):
        m = lab[s]["anomaly_type"].ne("Normal").to_numpy()
        v = err[s][m] if grp == "anomaly" else err[s][~m]
        stat_block(f"{s}:{grp}", v)
with (OUT / "153_stage11_reconstruction_error.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["scope", "group", "n", "min", "max", "mean", "median",
                              "std", "p1", "p5", "p25", "p50", "p75", "p90",
                              "p95", "p99"]] + rows153)

overlap = {}
for s in ("validation", "test"):
    m = lab[s]["anomaly_type"].ne("Normal").to_numpy()
    a, b_ = err[s][~m], err[s][m]
    lo, hi = float(min(a.min(), b_.min())), float(max(a.max(), b_.max()))
    ha, _ = np.histogram(a, bins=50, range=(lo, hi))
    hb, _ = np.histogram(b_, bins=50, range=(lo, hi))
    overlap[s] = round(float(np.minimum(ha, hb).sum() / min(ha.sum(), hb.sum())), 4)
print("threshold:", threshold, "| overlap:", overlap)

# ---------------- metrics 155 / per-type 156 --------------------------------
def metrics(split):
    m = lab[split]["anomaly_type"].ne("Normal").to_numpy()
    pred = err[split] > threshold
    tp = int((pred & m).sum()); tn = int((~pred & ~m).sum())
    fp = int((pred & ~m).sum()); fn = int((~pred & m).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    spec = tn / (tn + fp) if tn + fp else 0.0
    acc = (tp + tn) / len(m)
    fpr = fp / (fp + tn) if fp + tn else 0.0
    fnr = fn / (fn + tp) if fn + tp else 0.0
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4), "accuracy": round(float(acc), 4),
            "specificity": round(spec, 4), "fpr": round(fpr, 4),
            "fnr": round(fnr, 4),
            "n_normal_actual": int((~m).sum()), "n_anomaly_actual": int(m.sum()),
            "pred_normal_count": int((~pred).sum()),
            "pred_anomaly_count": int(pred.sum()),
            "flag_rate": round(float(pred.mean()), 4),
            "anomaly_rate_actual": round(float(m.mean()), 4)}

rows155 = []
for s in ("validation", "test"):
    mt = metrics(s)
    rows155.append([s, threshold, mt["tp"], mt["tn"], mt["fp"], mt["fn"],
                    mt["precision"], mt["recall"], mt["f1"], mt["accuracy"],
                    mt["specificity"], mt["fpr"], mt["fnr"],
                    mt["n_normal_actual"], mt["n_anomaly_actual"],
                    mt["pred_normal_count"], mt["pred_anomaly_count"],
                    mt["flag_rate"], mt["anomaly_rate_actual"]])
with (OUT / "155_stage11_evaluation_metrics.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["split", "threshold", "TP", "TN", "FP", "FN",
                              "precision", "recall", "f1", "accuracy",
                              "specificity", "FPR", "FNR",
                              "n_normal_actual", "n_anomaly_actual",
                              "pred_normal", "pred_anomaly",
                              "flag_rate", "actual_anomaly_rate"]] + rows155)

rows156 = []
for s in ("validation", "test"):
    at = lab[s]["anomaly_type"].to_numpy()
    pred = err[s] > threshold
    for t in sorted(set(at)):
        m = at == t
        det = int((pred & m).sum())
        rows156.append([s, t, int(m.sum()), det, int(m.sum()) - det,
                        round(det / int(m.sum()), 4)])
with (OUT / "156_stage11_anomaly_type_evaluation.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["split", "anomaly_type", "count", "detected",
                              "missed", "detection_rate"]] + rows156)
print("val:", metrics("validation"))
print("test:", metrics("test"))

# ---------------- old vs retrained (matched rows, per-pipeline prep) --------
comparison = {"status": "ATTEMPTED", "note": ""}
try:
    old_ckpt = torch.load(MODELS / "vae_model.pth", map_location="cpu",
                          weights_only=False)
    old_model = VariationalAutoencoder()
    old_model.load_state_dict(old_ckpt["model_state_dict"])
    old_model.eval()
    old_X = np.load(SVC / "dataset" / "preprocessed" / "X_train.npy")
    idx = np.concatenate([ids["validation"], ids["test"]])
    with torch.no_grad():
        b = torch.from_numpy(old_X[idx].astype(np.float32, copy=False))
        r, _, _ = old_model(b)
        old_err_all = torch.mean((b - r).pow(2), dim=1).cpu().numpy()
    old_thr = json.loads((MODELS / "deployment_config.json").read_text())["threshold"]
    n_val = len(ids["validation"])
    comparison["old"] = {}
    for s, sl in (("validation", slice(0, n_val)), ("test", slice(n_val, None))):
        m = lab[s]["anomaly_type"].ne("Normal").to_numpy()
        pred = old_err_all[sl] > old_thr
        tp = int((pred & m).sum()); fn = int((~pred & m).sum())
        fp = int((pred & ~m).sum()); tn = int((~pred & ~m).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        comparison["old"][s] = {
            "threshold": old_thr,
            "mean_recon": round(float(old_err_all[sl].mean()), 6),
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4)}
    comparison["caveat"] = ("model lama memakai preprocessing produksi lama "
                            "(scaler full-fit); model baru memakai final scaler "
                            "train-only â€” baris test identik, pipeline berbeda")
    comparison["status"] = "PARTIALLY COMPARABLE"
except Exception as exc:  # noqa: BLE001
    comparison = {"status": "NOT COMPARABLE", "note": repr(exc)}
print("comparison:", comparison.get("status"))

# ---------------- metadata & stats ------------------------------------------
param_count = sum(p.numel() for p in model.parameters())
hist_best = min(history, key=lambda h: h["val_loss"])
meta11 = {
    "script": "audit_l_stage11.py v1.0", "generated_at": started,
    "seed": {"python": SEED, "numpy": SEED, "torch": SEED},
    "deterministic_algorithms": True,
    "architecture": CONFIG,
    "parameter_count": param_count,
    "training_rows": int(len(data["train"])),
    "validation_rows": int(len(data["validation"])),
    "test_rows": int(len(data["test"])),
    "input_dimension": 9,
    "epochs_run": len(history),
    "best_epoch_by_validation_loss": hist_best["epoch"],
    "best_validation_loss": round(hist_best["val_loss"], 6),
    "final_train_loss": round(history[-1]["train_loss"], 6),
    "threshold_method": "P95 train reconstruction errors",
    "threshold": threshold,
    "status": "TRAINING VALIDATED / DEPLOYMENT NOT YET VALIDATED",
    "ip_inference_blocker": "OPEN -> Tahap 12",
    "artifacts": {
        "model": str(RT / "vae_model_stage11.pth"),
        "model_sha256": sha256_of(RT / "vae_model_stage11.pth"),
        "threshold": str(RT / "stage11_threshold.json"),
        "threshold_sha256": sha256_of(RT / "stage11_threshold.json")},
}
(RT / "stage11_model_metadata.json").write_text(json.dumps(meta11, indent=2), encoding="utf-8")
(OUT / "158_stage11_model_metadata.json").write_text(json.dumps(meta11, indent=2), encoding="utf-8")

stats11 = {"started": started, "input_ok": input_ok,
           "best_epoch": best["epoch"], "best_val_loss": best["val_total"],
           "final_train_loss": history[-1]["train_loss"],
           "threshold": threshold,
           "val_threshold_ref": val_threshold_ref,
           "overlap": overlap,
           "metrics_validation": metrics("validation"),
           "metrics_test": metrics("test"),
           "comparison": comparison,
           "param_count": param_count}
(OUT / "t11_stats.json").write_text(json.dumps(stats11, indent=2), encoding="utf-8")
print("[OK] artifacts saved to", RT)
