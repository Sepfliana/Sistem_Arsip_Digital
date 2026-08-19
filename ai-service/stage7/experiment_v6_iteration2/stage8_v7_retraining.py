"""
Stage 8 Iteration 2 -- V7 Targeted Fix + Retraining
=====================================================
Experiment-only.  Never modifies production artifacts.
Seed = 42 everywhere.  All outputs to experiment_v6_iteration2/.

Fix 1: Status preprocessing -- map unseen status to mode of train_normal
Fix 2: Localhost data split -- 70% train, 30% eval (no leakage)
"""
from __future__ import annotations
import hashlib, json, os, platform, random, sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    roc_auc_score, average_precision_score,
    precision_recall_curve, confusion_matrix,
)

# ── Paths ───────────────────────────────────────────────────────────────────
B = Path(__file__).resolve().parents[2]       # ai-service/
E = Path(__file__).resolve().parent            # experiment_v6_iteration2/
O = E / "retraining"
V6 = B / "stage7" / "v6"
sys.path.insert(0, str(B))

# ── Constants ───────────────────────────────────────────────────────────────
SEED = 42
EPOCHS = 100
BS = 64
LR = 0.001
BETA = 0.001
PROD_THRESHOLD = 3.1496288776397705
FEATURE_COLUMNS = [
    "user_id", "activity", "status", "device", "ip_address",
    "duration_ms", "object_count", "hour", "day_of_week",
]

PROD_FILES = [
    B / "models/vae_model.pth",
    B / "models/deployment_config.json",
    B / "dataset/preprocessed/scaler.pkl",
    B / "dataset/preprocessed/label_encoders.pkl",
    B / "dataset/preprocessed/X_train.npy",
]

# ── Helpers ─────────────────────────────────────────────────────────────────
def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def log(msg: str) -> None:
    print(f"  {msg}")


def summary_stats(x: np.ndarray) -> dict:
    return {
        "min": float(x.min()),
        "p25": float(np.quantile(x, 0.25)),
        "median": float(np.median(x)),
        "p75": float(np.quantile(x, 0.75)),
        "p95": float(np.quantile(x, 0.95)),
        "p99": float(np.quantile(x, 0.99)),
        "max": float(x.max()),
        "mean": float(x.mean()),
        "std": float(x.std()),
        "n": int(len(x)),
    }


# ═══════════════════════════════════════════════════════════════════════════
# V6 PREPROCESSING (copied from stage8_v6_retraining.py)
# ═══════════════════════════════════════════════════════════════════════════
V6_ACTIVITY_CLASSES = [
    "Login", "Logout", "Akses Berkas", "Kelola Berkas",
    "Kelola Perkara", "Kelola User", "Administrasi", "UNKNOWN",
]
V6_STATUS_CLASSES = ["Berhasil", "Gagal", "UNKNOWN"]
V6_DEVICE_CLASSES = [
    "PC Windows", "Android", "iOS", "Macos", "Linux",
    "Virtual Machine", "Unknown Device",
]
_ACTIVITY_REDUCTION = {
    "Keamanan & 2FA": "Administrasi",
    "Kelola Sarana": "Administrasi",
    "Peminjaman": "Administrasi",
    "Verifikasi": "Administrasi",
}


def map_network_scope(ip_input) -> str:
    ip_str = str(ip_input).strip().lower() if ip_input else ""
    if ip_str in ("127.0.0.1", "::1", "localhost", "0.0.0.0"):
        return "Internal"
    if "::ffff:" in ip_str:
        ip_str = ip_str.replace("::ffff:", "")
        if ip_str.startswith("127."):
            return "Internal"
    if ip_str.startswith("192.168.") or ip_str.startswith("10."):
        return "Internal"
    if ip_str.startswith("172."):
        try:
            octet = int(ip_str.split(".")[1])
            if 16 <= octet <= 31:
                return "Internal"
        except (IndexError, ValueError):
            pass
    import ipaddress
    try:
        addr = ipaddress.ip_address(ip_str)
        if addr.is_loopback or addr.is_private:
            return "Internal"
    except ValueError:
        pass
    return "External"


def map_has_telemetry(durasi_ms) -> float:
    try:
        return 1.0 if float(durasi_ms) > 0 else 0.0
    except (ValueError, TypeError):
        return 0.0


def map_time_period(hour: int) -> int:
    if 6 <= hour <= 11:
        return 0
    if 12 <= hour <= 17:
        return 1
    if 18 <= hour <= 23:
        return 2
    return 3


def map_activity_v6(activity_input) -> str:
    raw = str(activity_input).strip() if activity_input else ""
    if raw in _ACTIVITY_REDUCTION:
        return _ACTIVITY_REDUCTION[raw]
    if raw in V6_ACTIVITY_CLASSES:
        return raw
    return "UNKNOWN"


def parse_timestamp_wib(waktu_input):
    try:
        dt = pd.to_datetime(waktu_input)
        if dt.tzinfo is not None:
            dt = dt.tz_convert("Asia/Jakarta")
        else:
            dt = dt.tz_localize("UTC").tz_convert("Asia/Jakarta")
        return int(dt.hour), int(dt.dayofweek)
    except Exception:
        return 0, 0


# ── V6 Encoder / Scaler reconstruction from JSON ───────────────────────────
class V6Scaler:
    """Reconstruct StandardScaler from JSON mean/scale arrays."""
    def __init__(self, mean, scale):
        self.mean_ = np.array(mean, dtype=np.float64)
        self.scale_ = np.array(scale, dtype=np.float64)

    def transform(self, X: np.ndarray) -> np.ndarray:
        return ((X - self.mean_) / self.scale_).astype("float32")


def reconstruct_label_encoder(classes: list) -> LabelEncoder:
    """Build a LabelEncoder from a known class list (no .fit on data)."""
    le = LabelEncoder()
    le.classes_ = np.array(classes)
    return le


# ═══════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════
def main():
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True, warn_only=True)
    O.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("=" * 60)
    print("STAGE 8 -- V7 TARGETED FIX + RETRAINING")
    print("=" * 60)

    # ── Production hash snapshot ────────────────────────────────────────────
    before = {}
    for p in PROD_FILES:
        if p.exists():
            before[str(p.relative_to(B))] = sha(p)

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 1 -- DATA LOADING
    # ════════════════════════════════════════════════════════════════════════
    print("\n[Phase 1] Data Loading")
    raw = pd.read_csv(B / "dataset/retraining/retraining_dataset_combined_raw.csv",
                       encoding="utf-8-sig")
    v6_raw = pd.read_csv(V6 / "v6_anomaly_raw.csv")
    with open(V6 / "preprocessing_pipeline.json", encoding="utf-8") as f:
        pipeline = json.load(f)

    log(f"Raw dataset: {len(raw)} rows")
    log(f"V6 anomalies: {len(v6_raw)} rows")

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 2 -- SOURCE-AWARE SPLIT (with localhost split)
    # ════════════════════════════════════════════════════════════════════════
    print("\n[Phase 2] Source-Aware Split (V7: localhost split)")

    # 2a. Filter SYNTHETIC NORMAL
    normal = raw[
        (raw.source_type == "SYNTHETIC") & (raw.candidate_type == "NORMAL")
    ].copy()
    log(f"Synthetic normal: {len(normal)}")

    # 2b. Exclude V6 anomaly base_record_ids
    v6_base_ids = set(v6_raw["base_record_id"].astype(str))
    sources = set(normal["source_id"].astype(str))
    missing = v6_base_ids - sources
    if missing:
        log(f"WARNING: {len(missing)} V6 base ids not in source pool")
    excluded = normal[normal["source_id"].astype(str).isin(v6_base_ids)]
    pool = normal[~normal["source_id"].astype(str).isin(v6_base_ids)].copy()
    log(f"Excluded V6 base sources: {len(excluded)}")
    log(f"Pool after exclusion: {len(pool)}")

    # 2c. Split LOCALHOST into train (70%) and eval (30%) -- NO LEAKAGE
    lh_all = raw[raw.source_type == "REAL_DB"].copy()
    lh_all = lh_all.sample(frac=1, random_state=SEED).reset_index(drop=True)
    n_lh = len(lh_all)
    n_lh_train = int(0.7 * n_lh)
    lh_train = lh_all.iloc[:n_lh_train].copy()
    lh_eval = lh_all.iloc[n_lh_train:].copy()
    log(f"Localhost total:   {n_lh}")
    log(f"Localhost train:   {len(lh_train)} (70%)")
    log(f"Localhost eval:    {len(lh_eval)} (30%)")

    # 2d. Mix: 70% synthetic + 30% localhost for training
    #     Target: n_synthetic = n_lh_train / 0.30 - n_lh_train = n_lh_train * (70/30)
    n_synthetic_needed = int(n_lh_train * (70.0 / 30.0))
    pool_shuffled = pool.sample(frac=1, random_state=SEED).reset_index(drop=True)
    synthetic_train_pool = pool_shuffled.iloc[:n_synthetic_needed].copy()
    log(f"Synthetic for mix: {len(synthetic_train_pool)}")

    # Combine for training
    tr = pd.concat([synthetic_train_pool, lh_train], ignore_index=True)
    tr = tr.sample(frac=1, random_state=SEED).reset_index(drop=True)
    log(f"train_normal_v7:   {len(tr)} (70% syn + 30% lh)")

    # 2e. Validation and test: SYNTHETIC ONLY (no contamination)
    remaining_synthetic = pool_shuffled.iloc[n_synthetic_needed:].copy()
    n_remaining = len(remaining_synthetic)
    n_val = int(0.5 * n_remaining)  # split remaining 50/50 for val/test
    va = remaining_synthetic.iloc[:n_val].copy()
    te = remaining_synthetic.iloc[n_val:].copy()
    log(f"val_normal:   {len(va)} (synthetic only)")
    log(f"test_normal:  {len(te)} (synthetic only)")

    # 2f. Split V6 anomalies
    av = v6_raw.sample(frac=1, random_state=SEED).reset_index(drop=True)
    cut = len(av) // 2
    ava = av.iloc[:cut]
    ate = av.iloc[cut:]

    log(f"val_anomaly:  {len(ava)}")
    log(f"test_anomaly: {len(ate)}")

    # 2g. Assertions -- ZERO OVERLAP
    tr_src = set(tr["source_id"].astype(str))
    va_src = set(va["source_id"].astype(str))
    te_src = set(te["source_id"].astype(str))
    ava_base = set(ava["base_record_id"].astype(str))
    ate_base = set(ate["base_record_id"].astype(str))
    lh_train_src = set(lh_train["source_id"].astype(str))
    lh_eval_src = set(lh_eval["source_id"].astype(str))

    assert not (tr_src & va_src), "Overlap train/val normal"
    assert not (tr_src & te_src), "Overlap train/test normal"
    assert not (va_src & te_src), "Overlap val/test normal"
    assert not (tr_src & ava_base), "V6 anomaly base in train_normal"
    assert not (tr_src & ate_base), "V6 anomaly base in train_normal"
    assert not (va_src & ava_base), "V6 anomaly base in val_normal"
    assert not (va_src & ate_base), "V6 anomaly base in val_normal"
    assert not (te_src & ava_base), "V6 anomaly base in test_normal"
    assert not (te_src & ate_base), "V6 anomaly base in test_normal"
    assert not (ava_base & ate_base), "Overlap val/test anomaly bases"
    assert len(ava) + len(ate) == len(v6_raw), "Anomaly count mismatch"
    # CRITICAL: no localhost overlap between train and eval
    assert not (lh_train_src & lh_eval_src), "LOCALHOST LEAKAGE: train/eval overlap"
    assert len(lh_train) + len(lh_eval) == n_lh, "Localhost count mismatch"
    # Verify localhost is NOT in val/test normal
    assert not (lh_eval_src & va_src), "Localhost eval in val_normal"
    assert not (lh_eval_src & te_src), "Localhost eval in test_normal"
    log("Split assertions: PASS")

    # Save split metadata
    split_meta = {
        "synthetic_pool_after_exclusion": len(pool),
        "synthetic_train_mixed": len(synthetic_train_pool),
        "synthetic_val": len(va),
        "synthetic_test": len(te),
        "localhost_total": n_lh,
        "localhost_train": len(lh_train),
        "localhost_eval": len(lh_eval),
        "train_normal_v7_total": len(tr),
        "train_composition": "70% synthetic + 30% localhost",
        "val_anomaly": len(ava),
        "test_anomaly": len(ate),
        "assertions": "ALL PASS",
    }
    (E / "split_metadata.json").write_text(json.dumps(split_meta, indent=2), encoding="utf-8")

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 3 -- V6 ENCODE & SCALE (with status fix)
    # ════════════════════════════════════════════════════════════════════════
    print("\n[Phase 3] V6 Encode & Scale (V7: status fix)")

    # Reconstruct encoders from JSON (NO .fit on data)
    encoders = {}
    for feat in ["activity", "status", "device", "ip_address"]:
        classes = pipeline["encoders"][feat]["classes"]
        encoders[feat] = reconstruct_label_encoder(classes)
        log(f"Encoder {feat}: {len(classes)} classes")

    # Reconstruct scaler from JSON
    sc = V6Scaler(pipeline["scaler"]["mean"], pipeline["scaler"]["scale"])
    log(f"Scaler: mean={sc.mean_[:3]}... scale={sc.scale_[:3]}...")

    # FIX 1: Compute most frequent status from TRAIN_NORMAL ONLY
    # (before encoding, from the raw status column)
    train_raw_status = tr.get("status", pd.Series([])).fillna("").astype(str).str.strip()
    most_freq_status = train_raw_status.mode()
    if len(most_freq_status) > 0:
        most_freq_status = most_freq_status.iloc[0]
    else:
        most_freq_status = "Berhasil"  # fallback
    log(f"FIX 1: Most frequent train status: '{most_freq_status}'")
    log(f"  (will replace unseen status values with this)")

    # Vectorized V6 preprocessing with FIX 1
    def vectorized_v6_preprocess(df: pd.DataFrame, status_fallback: str) -> pd.DataFrame:
        """Apply V6 preprocessing vectorized across the DataFrame.
        FIX 1: Maps unseen status to status_fallback (mode of train_normal)."""
        c = pd.DataFrame()
        # user_id
        c["user_id"] = pd.to_numeric(df.get("user_id", 1), errors="coerce").fillna(1.0)
        # activity
        raw_act = df.get("aksi", df.get("activity", "")).fillna("").astype(str).str.strip()
        reduced = raw_act.map(_ACTIVITY_REDUCTION)
        c["activity"] = reduced.fillna(raw_act.where(raw_act.isin(V6_ACTIVITY_CLASSES), "UNKNOWN"))
        # status -- FIX 1: map unseen to mode of train_normal (not "UNKNOWN")
        raw_st = df.get("status", "").fillna("").astype(str).str.strip()
        c["status"] = raw_st.where(raw_st.isin(V6_STATUS_CLASSES), status_fallback)
        # device
        raw_dev = df.get("device", "").fillna("").astype(str).str.strip()
        mapped_dev = raw_dev.where(raw_dev.isin(V6_DEVICE_CLASSES), "Unknown Device")
        c["device"] = mapped_dev.replace("Unknown Device", "PC Windows")
        # ip_address (vectorized map_network_scope)
        ip_raw = df.get("ip_address", "").fillna("").astype(str).str.strip().str.lower()
        is_internal = (
            ip_raw.isin(["127.0.0.1", "::1", "localhost", "0.0.0.0"])
            | ip_raw.str.startswith("192.168.")
            | ip_raw.str.startswith("10.")
        )
        # 172.16-31.x.x (vectorized)
        starts_172 = ip_raw.str.startswith("172.")
        octets = ip_raw.str.split(".", expand=True)
        _172_mask = starts_172
        if octets.shape[1] > 1:
            try:
                oct2 = pd.to_numeric(octets[1], errors="coerce").fillna(0).astype(int)
                _172_mask = starts_172 & (oct2 >= 16) & (oct2 <= 31)
            except Exception:
                pass
        is_internal = is_internal | _172_mask
        # strip ::ffff: prefix
        ip_stripped = ip_raw.str.replace("::ffff:", "", regex=False)
        is_internal = is_internal | (ip_stripped.str.startswith("127.") & ~is_internal)
        c["ip_address"] = np.where(is_internal, "Internal", "External")
        # duration_ms -> binary has_telemetry
        dur = pd.to_numeric(df.get("durasi_ms", df.get("duration_ms", 0)), errors="coerce").fillna(0.0)
        c["duration_ms"] = (dur > 0).astype(float)
        # object_count -> log1p
        obj = pd.to_numeric(df.get("jumlah_objek", df.get("object_count", 0)), errors="coerce").fillna(0.0)
        obj = obj.clip(lower=0)
        c["object_count"] = np.log1p(obj)
        # hour -> 4 periods (vectorized timestamp parse)
        waktu_col = df.get("waktu", pd.Series([""] * len(df)))
        dt = pd.to_datetime(waktu_col, errors="coerce", utc=True)
        try:
            dt = dt.dt.tz_convert("Asia/Jakarta")
        except TypeError:
            dt = dt.dt.tz_localize("UTC").dt.tz_convert("Asia/Jakarta")
        hours_raw = dt.dt.hour.fillna(0).astype(int)
        c["hour"] = pd.cut(hours_raw, bins=[-1, 5, 11, 17, 23], labels=[3, 0, 1, 2]).astype(int)
        # day_of_week
        c["day_of_week"] = dt.dt.dayofweek.fillna(0).astype(int)
        return c

    def encode_partition(df: pd.DataFrame) -> np.ndarray:
        """Apply V6 vectorized preprocess -> encode -> scale."""
        canon = vectorized_v6_preprocess(df, most_freq_status)
        encoded_cols = []
        for feat in ["activity", "status", "device", "ip_address"]:
            col = canon[feat].copy()
            known = set(encoders[feat].classes_)
            col = col.where(col.isin(known), encoders[feat].classes_[0])
            encoded_cols.append(encoders[feat].transform(col).astype(float))
        X = np.column_stack([
            canon["user_id"].astype(float),
            *encoded_cols,
            canon["duration_ms"].astype(float),
            canon["object_count"].astype(float),
            canon["hour"].astype(float),
            canon["day_of_week"].astype(float),
        ])
        return sc.transform(X).astype("float32")

    Xtr = encode_partition(tr)
    Xv  = encode_partition(va)
    Xt  = encode_partition(te)
    Xva = encode_partition(ava)
    Xta = encode_partition(ate)
    Xlh_eval = encode_partition(lh_eval)  # EVALUATION localhost only
    Xlh_train = encode_partition(lh_train)  # TRAINING localhost (for reference)

    for name, X in [("train", Xtr), ("val_norm", Xv), ("test_norm", Xt),
                     ("val_anom", Xva), ("test_anom", Xta),
                     ("localhost_eval", Xlh_eval), ("localhost_train", Xlh_train)]:
        assert X.shape[1] == 9, f"{name}: wrong features {X.shape}"
        assert not np.isnan(X).any(), f"{name}: NaN"
        assert not np.isinf(X).any(), f"{name}: Inf"
    log(f"Train matrix: {Xtr.shape}")
    log(f"Localhost eval matrix: {Xlh_eval.shape}")
    log("Encode assertions: PASS")

    # Save manifests
    tr.to_csv(E / "train_normal_manifest.csv", index=False)
    va.to_csv(E / "validation_normal_manifest.csv", index=False)
    te.to_csv(E / "test_normal_manifest.csv", index=False)
    ava.to_csv(E / "validation_anomaly_manifest.csv", index=False)
    ate.to_csv(E / "test_anomaly_manifest.csv", index=False)
    lh_train.to_csv(E / "localhost_train_manifest.csv", index=False)
    lh_eval.to_csv(E / "localhost_eval_manifest.csv", index=False)

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 4 -- TRAIN VAE
    # ════════════════════════════════════════════════════════════════════════
    print("\n[Phase 4] Train VAE")

    from services.model_loader import VariationalAutoencoder

    model = VariationalAutoencoder().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    gen = torch.Generator().manual_seed(SEED)
    loader = DataLoader(
        TensorDataset(torch.from_numpy(Xtr)),
        batch_size=BS, shuffle=True, generator=gen,
    )

    hist = []
    for ep in range(EPOCHS):
        model.train()
        tot = rec = kl = 0.0
        for (x,) in loader:
            x = x.float().to(device)
            optimizer.zero_grad()
            o, mu, lv = model(x)
            r = F.mse_loss(o, x)
            k = -0.5 * torch.mean(1 + lv - mu.pow(2) - lv.exp())
            loss = r + BETA * k
            loss.backward()
            optimizer.step()
            tot += loss.item() * len(x)
            rec += r.item() * len(x)
            kl += k.item() * len(x)
        # Validation loss
        model.eval()
        with torch.no_grad():
            q = torch.from_numpy(Xv).float().to(device)
            o, mu, lv = model(q)
            vr = F.mse_loss(o, q).item()
            vk = (-0.5 * torch.mean(1 + lv - mu.pow(2) - lv.exp())).item()
        hist.append({
            "epoch": ep + 1,
            "train_total": tot / len(Xtr),
            "train_reconstruction": rec / len(Xtr),
            "train_kl": kl / len(Xtr),
            "val_normal_total": vr + BETA * vk,
            "val_normal_reconstruction": vr,
            "val_normal_kl": vk,
        })
        if (ep + 1) % 20 == 0 or ep == 0:
            log(f"Epoch {ep+1:3d}: loss={tot/len(Xtr):.6f}  val_recon={vr:.6f}")

    final_loss = hist[-1]["train_total"]
    log(f"Final train loss: {final_loss:.6f}")

    # Save checkpoint
    ck = O / "vae_model_v7_experiment.pth"
    torch.save(model.state_dict(), ck)
    log(f"Saved checkpoint: {ck.name}")

    # Verify reload
    model2 = VariationalAutoencoder().to(device)
    model2.load_state_dict(torch.load(ck, map_location=device, weights_only=False))
    model2.eval()
    with torch.no_grad():
        test_x = torch.from_numpy(Xtr[:5]).float().to(device)
        _, mu1, _ = model(test_x)
        _, mu2, _ = model2(test_x)
        assert torch.allclose(mu1, mu2, atol=1e-6), "Reload mismatch"
    log("Checkpoint reload: PASS")

    # Save training artifacts
    pd.DataFrame(hist).to_csv(O / "training_loss.csv", index=False)
    (O / "training_history.json").write_text(json.dumps(hist, indent=2), encoding="utf-8")
    cfg = {
        "seed": SEED, "epochs": EPOCHS, "batch_size": BS,
        "learning_rate": LR, "beta_kl": BETA,
        "architecture": "9-64-32-8-32-64-9 ReLU Dropout(0.2)",
        "device": str(device), "torch": torch.__version__,
        "python": platform.python_version(),
        "input_features": FEATURE_COLUMNS,
        "v7_fixes": {
            "status_fallback": most_freq_status,
            "training_composition": "70% synthetic + 30% localhost",
        },
    }
    (O / "training_config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 5 -- EVALUATION
    # ════════════════════════════════════════════════════════════════════════
    print("\n[Phase 5] Evaluation")

    def mse(model, X):
        model.eval()
        with torch.no_grad():
            q = torch.from_numpy(X).float().to(device)
            encoded = model.encoder(q)
            mu = model.mu(encoded)
            recon = model.decoder(mu)
            return (q - recon).pow(2).mean(dim=1).cpu().numpy()

    ev       = mse(model2, Xv)         # val_normal (synthetic)
    et       = mse(model2, Xt)         # test_normal (synthetic)
    eva      = mse(model2, Xva)        # val_anomaly
    eta      = mse(model2, Xta)        # test_anomaly
    elh_eval = mse(model2, Xlh_eval)   # localhost_eval (30%)
    elh_train = mse(model2, Xlh_train) # localhost_train (70%, for reference)

    log(f"val_normal      MSE: {ev.mean():.6f}  (n={len(ev)})")
    log(f"test_normal     MSE: {et.mean():.6f}  (n={len(et)})")
    log(f"val_anomaly     MSE: {eva.mean():.6f}  (n={len(eva)})")
    log(f"test_anomaly    MSE: {eta.mean():.6f}  (n={len(eta)})")
    log(f"localhost_eval  MSE: {elh_eval.mean():.6f}  (n={len(elh_eval)})")
    log(f"localhost_train MSE: {elh_train.mean():.6f}  (n={len(elh_train)})")

    # Threshold from validation (max F1)
    y_val = np.r_[np.zeros(len(ev)), np.ones(len(eva))]
    s_val = np.r_[ev, eva]
    pr, re, th = precision_recall_curve(y_val, s_val)
    f1s = 2 * pr * re / (pr + re + 1e-12)
    best_idx = int(f1s.argmax())
    threshold_f1 = float(th[min(best_idx, len(th) - 1)])

    # Safe thresholds
    threshold_safe_p95 = float(np.percentile(ev, 95))
    threshold_safe_p99 = float(np.percentile(ev, 99))
    threshold_safe_p995 = float(np.percentile(ev, 99.5))
    threshold_max_val = float(np.max(ev))

    log(f"Threshold (F1 optimal): {threshold_f1:.6f}")
    log(f"Threshold (safe P95):   {threshold_safe_p95:.6f}")
    log(f"Threshold (safe P99):   {threshold_safe_p99:.6f}")
    log(f"Threshold (safe P99.5): {threshold_safe_p995:.6f}")
    log(f"Threshold (max val):    {threshold_max_val:.6f}")

    # Test metrics at F1 threshold
    y_test = np.r_[np.zeros(len(et)), np.ones(len(eta))]
    s_test = np.r_[et, eta]
    roc_auc = roc_auc_score(y_test, s_test)
    pr_auc  = average_precision_score(y_test, s_test)
    pred_f1 = s_test >= threshold_f1
    tn, fp, fn, tp = confusion_matrix(y_test, pred_f1).ravel()
    f1  = 2 * tp / (2 * tp + fp + fn)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec  = tp / (tp + fn) if (tp + fn) > 0 else 0
    fpr  = fp / (fp + tn) if (fp + tn) > 0 else 0

    log(f"ROC-AUC: {roc_auc:.4f}")
    log(f"PR-AUC:  {pr_auc:.4f}")
    log(f"F1:      {f1:.4f}")
    log(f"Precision: {prec:.4f}  Recall: {rec:.4f}  FPR: {fpr:.4f}")

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 6 -- LOCALHOST SAFETY (CRITICAL)
    # ════════════════════════════════════════════════════════════════════════
    print("\n[Phase 6] Localhost Safety (using localhost_eval ONLY)")

    thresholds_to_test = {
        "validation_f1_optimal": threshold_f1,
        "safe_p95": threshold_safe_p95,
        "safe_p99": threshold_safe_p99,
        "safe_p995": threshold_safe_p995,
        "max_val_normal": threshold_max_val,
        "production": PROD_THRESHOLD,
    }

    safety = {}
    for name, thr in thresholds_to_test.items():
        fp = int((elh_eval >= thr).sum())
        fpr_val = float((elh_eval >= thr).mean())
        safety[name] = {
            "threshold": round(thr, 6),
            "localhost_eval_fp": fp,
            "localhost_eval_fpr": round(fpr_val, 4),
            "localhost_eval_n": len(elh_eval),
        }
        log(f"  {name:25s} thr={thr:.6f}  FPR={fpr_val:.4f}  FP={fp}/{len(elh_eval)}")

    # Domain gap (using localhost_eval)
    lh_min = float(elh_eval.min())
    lh_max = float(elh_eval.max())
    nh_max = float(np.max([ev.max(), et.max()]))
    gap = lh_min - nh_max
    log(f"  Domain gap:")
    log(f"    localhost_eval_min_mse:  {lh_min:.6f}")
    log(f"    localhost_eval_max_mse:  {lh_max:.6f}")
    log(f"    normal_max_mse:          {nh_max:.6f}")
    log(f"    gap (lh_min - n_max):    {gap:.6f}")

    (O / "localhost_safety.json").write_text(json.dumps(safety, indent=2), encoding="utf-8")

    # Distribution stats
    dist = pd.DataFrame([
        {"group": "validation_normal", **summary_stats(ev)},
        {"group": "test_normal", **summary_stats(et)},
        {"group": "validation_anomaly", **summary_stats(eva)},
        {"group": "test_anomaly", **summary_stats(eta)},
        {"group": "localhost_eval", **summary_stats(elh_eval)},
        {"group": "localhost_train", **summary_stats(elh_train)},
    ])
    dist.to_csv(O / "evaluation_distributions.csv", index=False)

    # Threshold sweep (using localhost_eval)
    sweep_rows = []
    for thr in np.linspace(0.001, 3.0, 600):
        fp_lh = int((elh_eval >= thr).sum())
        fn_t  = int((eta < thr).sum())
        tp_t  = int((eta >= thr).sum())
        tn_t  = int((et < thr).sum())
        fp_t  = int((et >= thr).sum())
        p  = tp_t / (tp_t + fp_t) if (tp_t + fp_t) > 0 else 0
        r  = tp_t / (tp_t + fn_t) if (tp_t + fn_t) > 0 else 0
        f  = 2 * p * r / (p + r + 1e-12)
        fpr_t = fp_t / (fp_t + tn_t) if (fp_t + tn_t) > 0 else 0
        sweep_rows.append({
            "threshold": round(float(thr), 6),
            "test_f1": round(f, 4),
            "test_precision": round(p, 4),
            "test_recall": round(r, 4),
            "test_fpr": round(fpr_t, 4),
            "localhost_eval_fp": fp_lh,
            "localhost_eval_fpr": round(float(fp_lh / len(elh_eval)), 4),
        })
    pd.DataFrame(sweep_rows).to_csv(O / "threshold_sweep.csv", index=False)

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 7 -- OUTPUT FILES
    # ════════════════════════════════════════════════════════════════════════
    print("\n[Phase 7] Output Files")

    metrics = {
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "f1": round(f1, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "fpr": round(fpr, 4),
        "threshold_f1_optimal": round(threshold_f1, 6),
        "threshold_safe_p95": round(threshold_safe_p95, 6),
        "threshold_safe_p99": round(threshold_safe_p99, 6),
        "threshold_safe_p995": round(threshold_safe_p995, 6),
        "threshold_max_val_normal": round(threshold_max_val, 6),
    }
    (O / "evaluation_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    ck_sha = sha(ck) if ck.exists() else None
    meta = {
        "stage": "8",
        "version": "V7",
        "iteration": 2,
        "seed": SEED,
        "checkpoint_sha256": ck_sha,
        "checkpoint_reload": "PASS",
        "v7_fixes": {
            "status_fallback": most_freq_status,
            "training_composition": "70% synthetic + 30% localhost",
        },
        "metrics": metrics,
        "localhost_safety": safety,
        "domain_gap": {
            "localhost_eval_min": lh_min,
            "localhost_eval_max": lh_max,
            "normal_max": nh_max,
            "gap": gap,
        },
        "production_before": before,
        "production_after": {str(p.relative_to(B)): sha(p) for p in PROD_FILES if p.exists()},
    }
    (O / "experiment_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (O / "model_summary.json").write_text(json.dumps({
        "architecture": cfg["architecture"],
        "input_features": FEATURE_COLUMNS,
        "training_rows": len(Xtr),
        "training_composition": "70% synthetic + 30% localhost",
    }, indent=2), encoding="utf-8")

    # ── Training report ─────────────────────────────────────────────────────
    report = f"""# Stage 8 Iteration 2 -- V7 Targeted Fix + Retraining

Experiment-only checkpoint.  No production deployment.

## Configuration
- Architecture: {cfg['architecture']}
- Training: {EPOCHS} epochs, lr={LR}, beta_kl={BETA}, batch_size={BS}
- V7 Fixes:
  1. Status preprocessing: unseen status -> '{most_freq_status}' (mode of train_normal)
  2. Training data: 70% synthetic + 30% localhost (no leakage)
- Train rows: {len(Xtr)}

## Final Training Loss
{final_loss:.6f}

## Test Set Metrics
```json
{json.dumps(metrics, indent=2)}
```

## Localhost Safety (using localhost_eval only)
```json
{json.dumps(safety, indent=2)}
```

## Domain Gap
- localhost_eval_min_mse: {lh_min:.6f}
- localhost_eval_max_mse: {lh_max:.6f}
- normal_max_mse: {nh_max:.6f}
- gap: {gap:.6f}

## Production Integrity
- Match: {before == meta['production_after']}
"""
    (O / "training_report.md").write_text(report, encoding="utf-8")

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 8 -- DECISION GATE
    # ════════════════════════════════════════════════════════════════════════
    print("\n[Phase 8] Decision Gate")

    lh_fpr_f1 = safety["validation_f1_optimal"]["localhost_eval_fpr"]
    lh_fpr_p99 = safety["safe_p99"]["localhost_eval_fpr"]
    lh_fpr_prod = safety["production"]["localhost_eval_fpr"]

    pass_f1 = f1 >= 0.80
    pass_fpr = lh_fpr_f1 < 0.20
    pass_gap = gap > -0.5

    if pass_f1 and pass_fpr:
        decision = "EXPERIMENT SUCCESS"
        verdict = "PASS"
    else:
        decision = "EXPERIMENT FAIL"
        verdict = "FAIL"

    gate = f"""# Stage 8 -- V7 Retraining Decision Gate

**Date:** Stage 8 iteration 2
**Scope:** Experiment-only retraining. No deployment.

---

## V7 Fixes Applied
1. Status preprocessing: unseen status -> '{most_freq_status}' (mode of train_normal)
2. Training data: 70% synthetic + 30% localhost (no leakage)

## Test Performance

| Metric | V6 | V7 |
|--------|-----|-----|
| ROC-AUC | 1.0000 | {roc_auc:.4f} |
| PR-AUC | 0.9999 | {pr_auc:.4f} |
| F1 | 0.9990 | {f1:.4f} |
| Precision | 0.998 | {prec:.4f} |
| Recall | 1.000 | {rec:.4f} |

## Localhost Safety (eval only)

| Threshold | FPR |
|-----------|-----|
| F1 optimal ({threshold_f1:.6f}) | {lh_fpr_f1:.2%} |
| P99 ({threshold_safe_p99:.6f}) | {lh_fpr_p99:.2%} |
| Production ({PROD_THRESHOLD:.6f}) | {lh_fpr_prod:.2%} |

## Domain Gap

| Metric | V6 | V7 |
|--------|-----|-----|
| localhost_eval_min_mse | 2.1829 | {lh_min:.6f} |
| localhost_eval_max_mse | 2.856 | {lh_max:.6f} |
| normal_max_mse | 0.1883 | {nh_max:.6f} |
| gap | 1.9946 | {gap:.6f} |

## Criteria

| Criterion | Threshold | Actual | Pass? |
|-----------|-----------|--------|-------|
| F1 >= 0.80 | >=0.80 | {f1:.4f} | {"PASS" if pass_f1 else "FAIL"} |
| Localhost FPR < 20% | <20% | {lh_fpr_f1:.2%} | {"PASS" if pass_fpr else "FAIL"} |

## Decision

**{decision}**

{"V7 targeted fixes resolve localhost domain gap. Eligible for Stage 9." if verdict == "PASS" else "V7 fixes did not fully resolve localhost FPR. Consider additional fixes."}

---

## Next Step

{"-> Proceed to Stage 9: Threshold calibration and production readiness" if verdict == "PASS" else "-> Investigate remaining domain gap; consider additional preprocessing or architecture changes"}
"""
    (E / "STAGE_8_DECISION.md").write_text(gate, encoding="utf-8")

    # ── Final print ─────────────────────────────────────────────────────────
    prod_match = before == meta["production_after"]
    print("\n" + "=" * 60)
    print("STAGE 8 -- V7 RESULTS")
    print("=" * 60)
    print(f"\nROC-AUC: {roc_auc:.4f}")
    print(f"PR-AUC:  {pr_auc:.4f}")
    print(f"F1:      {f1:.4f}")
    print(f"\nMSE:")
    print(f"  train_normal_mean:    {ev.mean():.6f}")
    print(f"  localhost_eval_mean:  {elh_eval.mean():.6f}")
    print(f"  gap:                  {gap:.6f}")
    print(f"\nLOCALHOST FPR:")
    print(f"  F1 threshold:  {lh_fpr_f1:.2%}")
    print(f"  P99:           {lh_fpr_p99:.2%}")
    print(f"  production:    {lh_fpr_prod:.2%}")
    print(f"\nDECISION:")
    print(f"  -> {decision}")
    print(f"\nProduction integrity: {'VERIFIED' if prod_match else 'COMPROMISED'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
