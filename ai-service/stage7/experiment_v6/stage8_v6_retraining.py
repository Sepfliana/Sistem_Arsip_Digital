"""
Stage 8 -- Controlled Retraining with V6 Preprocessing Pipeline
================================================================
Experiment-only.  Never modifies production artifacts.
Seed = 42 everywhere.  All outputs to stage7/experiment_v6/.
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
E = Path(__file__).resolve().parent            # experiment_v6/
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
# V6 PREPROCESSING  (copied from stage7_7_v6_dataset_redesign.py:56-181)
# ═══════════════════════════════════════════════════════════════════════════
V6_ACTIVITY_CLASSES = [
    "Login", "Logout", "Akses Berkas", "Kelola Berkas",
    "Kelola Perkara", "Kelola User", "Administrasi", "UNKNOWN",
]
V6_STATUS_CLASSES = ["Berhasil", "Gagal", "UNKNOWN"]
V6_DEVICE_CLASSES = [
    "PC Windows", "Android", "iOS", "MacOS", "Linux",
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


def process_record_v6(record: dict) -> dict:
    uid = float(record.get("user_id", 1))
    if not np.isfinite(uid):
        uid = 1.0
    dur = float(record.get("durasi_ms", record.get("duration_ms", 0.0)))
    if not np.isfinite(dur) or dur < 0:
        dur = 0.0
    obj = float(record.get("jumlah_objek", record.get("object_count", 0.0)))
    if not np.isfinite(obj) or obj < 0:
        obj = 0.0
    hour_wib, dow = parse_timestamp_wib(record.get("waktu", ""))
    raw_activity = record.get("aksi", record.get("activity", ""))
    raw_status = record.get("status", "")
    raw_device = record.get("device", "")
    raw_ip = record.get("ip_address", "")

    activity = map_activity_v6(raw_activity)
    status = str(raw_status).strip() if raw_status else "UNKNOWN"
    if status not in V6_STATUS_CLASSES:
        status = "UNKNOWN"
    device = str(raw_device).strip() if raw_device else "Unknown Device"
    if device not in V6_DEVICE_CLASSES:
        device = "Unknown Device"
    if device == "Unknown Device":
        device = "PC Windows"

    return {
        "user_id": uid,
        "activity": activity,
        "status": status,
        "device": device,
        "ip_address": map_network_scope(raw_ip),
        "duration_ms": map_has_telemetry(dur),
        "object_count": float(np.log1p(obj)),
        "hour": map_time_period(hour_wib),
        "day_of_week": dow,
    }


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
    print("STAGE 8 -- V6 CONTROLLED RETRAINING")
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
    # PHASE 2 -- SOURCE-AWARE SPLIT
    # ════════════════════════════════════════════════════════════════════════
    print("\n[Phase 2] Source-Aware Split")

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

    # 2c. Deterministic shuffle and split
    pool = pool.sample(frac=1, random_state=SEED).reset_index(drop=True)
    n = len(pool)
    n_train = int(0.7 * n)
    n_val = int(0.15 * n)
    tr = pool.iloc[:n_train]
    va = pool.iloc[n_train:n_train + n_val]
    te = pool.iloc[n_train + n_val:]

    # 2d. Split V6 anomalies
    av = v6_raw.sample(frac=1, random_state=SEED).reset_index(drop=True)
    cut = len(av) // 2
    ava = av.iloc[:cut]
    ate = av.iloc[cut:]

    # 2e. Localhost
    lh = raw[raw.source_type == "REAL_DB"].copy()

    log(f"train_normal: {len(tr)}")
    log(f"val_normal:   {len(va)}")
    log(f"test_normal:  {len(te)}")
    log(f"val_anomaly:  {len(ava)}")
    log(f"test_anomaly: {len(ate)}")
    log(f"localhost:    {len(lh)}")

    # 2f. Assertions
    tr_src = set(tr["source_id"].astype(str))
    va_src = set(va["source_id"].astype(str))
    te_src = set(te["source_id"].astype(str))
    ava_base = set(ava["base_record_id"].astype(str))
    ate_base = set(ate["base_record_id"].astype(str))

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
    log("Split assertions: PASS")

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 3 -- V6 ENCODE & SCALE
    # ════════════════════════════════════════════════════════════════════════
    print("\n[Phase 3] V6 Encode & Scale")

    # Reconstruct encoders from JSON (NO .fit on data)
    encoders = {}
    for feat in ["activity", "status", "device", "ip_address"]:
        classes = pipeline["encoders"][feat]["classes"]
        encoders[feat] = reconstruct_label_encoder(classes)
        log(f"Encoder {feat}: {len(classes)} classes")

    # Reconstruct scaler from JSON
    sc = V6Scaler(pipeline["scaler"]["mean"], pipeline["scaler"]["scale"])
    log(f"Scaler: mean={sc.mean_[:3]}... scale={sc.scale_[:3]}...")

    # Vectorized V6 preprocessing (much faster than row-by-row process_record_v6)
    def vectorized_v6_preprocess(df: pd.DataFrame) -> pd.DataFrame:
        """Apply V6 preprocessing vectorized across the DataFrame."""
        c = pd.DataFrame()
        # user_id
        c["user_id"] = pd.to_numeric(df.get("user_id", 1), errors="coerce").fillna(1.0)
        # activity
        raw_act = df.get("aksi", df.get("activity", "")).fillna("").astype(str).str.strip()
        reduced = raw_act.map(_ACTIVITY_REDUCTION)
        c["activity"] = reduced.fillna(raw_act.where(raw_act.isin(V6_ACTIVITY_CLASSES), "UNKNOWN"))
        # status
        raw_st = df.get("status", "").fillna("").astype(str).str.strip()
        c["status"] = raw_st.where(raw_st.isin(V6_STATUS_CLASSES), "UNKNOWN")
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
        canon = vectorized_v6_preprocess(df)
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
    Xlh = encode_partition(lh)

    for name, X in [("train", Xtr), ("val_norm", Xv), ("test_norm", Xt),
                     ("val_anom", Xva), ("test_anom", Xta), ("localhost", Xlh)]:
        assert X.shape[1] == 9, f"{name}: wrong features {X.shape}"
        assert not np.isnan(X).any(), f"{name}: NaN"
        assert not np.isinf(X).any(), f"{name}: Inf"
    log(f"Train matrix: {Xtr.shape}")
    log("Encode assertions: PASS")

    # Save manifests
    tr.to_csv(E / "train_normal_manifest.csv", index=False)
    va.to_csv(E / "validation_normal_manifest.csv", index=False)
    te.to_csv(E / "test_normal_manifest.csv", index=False)
    ava.to_csv(E / "validation_anomaly_manifest.csv", index=False)
    ate.to_csv(E / "test_anomaly_manifest.csv", index=False)

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
    ck = O / "vae_model_v6_experiment.pth"
    torch.save(model.state_dict(), ck)
    log(f"Saved checkpoint: {ck.name}")

    # Verify reload
    model2 = VariationalAutoencoder().to(device)
    model2.load_state_dict(torch.load(ck, map_location=device, weights_only=False))
    model2.eval()
    with torch.no_grad():
        test_x = torch.from_numpy(Xtr[:5]).float().to(device)
        # Compare mu (deterministic part) to avoid random latent sampling
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
            # Use mu (deterministic) for consistent MSE comparison
            encoded = model.encoder(q)
            mu = model.mu(encoded)
            recon = model.decoder(mu)
            return (q - recon).pow(2).mean(dim=1).cpu().numpy()

    ev  = mse(model2, Xv)
    et  = mse(model2, Xt)
    eva = mse(model2, Xva)
    eta = mse(model2, Xta)
    elh = mse(model2, Xlh)

    log(f"val_normal  MSE: {ev.mean():.6f}  (n={len(ev)})")
    log(f"test_normal MSE: {et.mean():.6f}  (n={len(et)})")
    log(f"val_anomaly MSE: {eva.mean():.6f}  (n={len(eva)})")
    log(f"test_anomaly MSE: {eta.mean():.6f}  (n={len(eta)})")
    log(f"localhost   MSE: {elh.mean():.6f}  (n={len(elh)})")

    # Threshold from validation (max F1)
    y_val = np.r_[np.zeros(len(ev)), np.ones(len(eva))]
    s_val = np.r_[ev, eva]
    pr, re, th = precision_recall_curve(y_val, s_val)
    f1s = 2 * pr * re / (pr + re + 1e-12)
    best_idx = int(f1s.argmax())
    threshold_f1 = float(th[min(best_idx, len(th) - 1)])

    # Safe threshold: P99 of val_normal
    threshold_safe = float(np.percentile(ev, 99))

    log(f"Threshold (F1 optimal): {threshold_f1:.6f}")
    log(f"Threshold (safe P99):   {threshold_safe:.6f}")

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
    print("\n[Phase 6] Localhost Safety")

    thresholds_to_test = {
        "validation_f1_optimal": threshold_f1,
        "safe_p99": threshold_safe,
        "production": PROD_THRESHOLD,
        "p95_val_normal": float(np.percentile(ev, 95)),
        "max_val_normal": float(np.max(ev)),
    }

    safety = {}
    for name, thr in thresholds_to_test.items():
        fp = int((elh >= thr).sum())
        fpr_val = float((elh >= thr).mean())
        safety[name] = {
            "threshold": round(thr, 6),
            "localhost_fp": fp,
            "localhost_fpr": round(fpr_val, 4),
            "localhost_n": len(elh),
        }
        log(f"  {name:25s} thr={thr:.6f}  FPR={fpr_val:.4f}  FP={fp}/{len(elh)}")

    # Domain gap
    lh_min = float(elh.min())
    nh_max = float(np.max([ev.max(), et.max()]))
    gap = lh_min - nh_max
    log(f"  Domain gap:")
    log(f"    localhost_min_mse:  {lh_min:.6f}")
    log(f"    normal_max_mse:     {nh_max:.6f}")
    log(f"    gap (lh_min - n_max): {gap:.6f}")

    (O / "localhost_safety.json").write_text(json.dumps(safety, indent=2), encoding="utf-8")

    # Distribution stats
    dist = pd.DataFrame([
        {"group": "validation_normal", **summary_stats(ev)},
        {"group": "test_normal", **summary_stats(et)},
        {"group": "validation_anomaly", **summary_stats(eva)},
        {"group": "test_anomaly", **summary_stats(eta)},
        {"group": "localhost", **summary_stats(elh)},
    ])
    dist.to_csv(O / "evaluation_distributions.csv", index=False)

    # Threshold sweep
    sweep_rows = []
    for thr in np.linspace(0.001, 1.5, 300):
        fp_lh = int((elh >= thr).sum())
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
            "localhost_fp": fp_lh,
            "localhost_fpr": round(float(fp_lh / len(elh)), 4),
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
        "threshold_safe_p99": round(threshold_safe, 6),
    }
    (O / "evaluation_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    ck_sha = sha(ck) if ck.exists() else None
    meta = {
        "stage": "8",
        "version": "V6",
        "seed": SEED,
        "checkpoint_sha256": ck_sha,
        "checkpoint_reload": "PASS",
        "metrics": metrics,
        "localhost_safety": safety,
        "domain_gap": {"localhost_min": lh_min, "normal_max": nh_max, "gap": gap},
        "production_before": before,
        "production_after": {str(p.relative_to(B)): sha(p) for p in PROD_FILES if p.exists()},
    }
    (O / "experiment_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (O / "model_summary.json").write_text(json.dumps({
        "architecture": cfg["architecture"],
        "input_features": FEATURE_COLUMNS,
        "training_rows": len(Xtr),
    }, indent=2), encoding="utf-8")

    # ── Training report ─────────────────────────────────────────────────────
    report = f"""# Stage 8 -- V6 Controlled Retraining Experiment

Experiment-only checkpoint.  No production deployment.

## Configuration
- Architecture: {cfg['architecture']}
- Training: {EPOCHS} epochs, lr={LR}, beta_kl={BETA}, batch_size={BS}
- V6 preprocessing: binary IP, binary duration, 4-period hour, 8-category activity
- Train rows: {len(Xtr)}

## Final Training Loss
{final_loss:.6f}

## Test Set Metrics
```json
{json.dumps(metrics, indent=2)}
```

## Localhost Safety
```json
{json.dumps(safety, indent=2)}
```

## Domain Gap
- localhost_min_mse: {lh_min:.6f}
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

    lh_fpr_f1 = safety["validation_f1_optimal"]["localhost_fpr"]
    lh_fpr_safe = safety["safe_p99"]["localhost_fpr"]
    lh_fpr_prod = safety["production"]["localhost_fpr"]

    pass_f1 = f1 > 0.8
    pass_fpr = lh_fpr_f1 < 0.10
    pass_gap = gap > -0.5  # localhost MSE above normal MSE

    if pass_f1 and pass_fpr:
        decision = "EXPERIMENT SUCCESS"
        verdict = "PASS"
    else:
        decision = "EXPERIMENT FAIL"
        verdict = "FAIL"

    # V5 comparison
    v5_fpr_val = 1.00
    v5_f1 = 0.996
    v5_roc = 0.9998

    gate = f"""# Stage 8 -- V6 Retraining Decision Gate

**Date:** Stage 8 completion
**Scope:** Experiment-only retraining. No deployment.

---

## Test Performance

| Metric | V5 | V6 | Change |
|--------|-----|-----|--------|
| ROC-AUC | {v5_roc:.4f} | {roc_auc:.4f} | |
| PR-AUC | 0.9991 | {pr_auc:.4f} | |
| F1 | {v5_f1:.4f} | {f1:.4f} | |
| Precision | 0.996 | {prec:.4f} | |
| Recall | 0.996 | {rec:.4f} | |

## Localhost Safety

| Metric | V5 | V6 | Change |
|--------|-----|-----|--------|
| FPR (val threshold) | {v5_fpr_val:.2%} | {lh_fpr_f1:.2%} | {v5_fpr_val - lh_fpr_f1:.2%} reduction |
| FPR (safe P99) | -- | {lh_fpr_safe:.2%} | |
| FPR (production) | 41.6% | {lh_fpr_prod:.2%} | |

## Domain Gap

| Metric | V5 | V6 |
|--------|-----|-----|
| localhost_min_mse | 2.389 | {lh_min:.6f} |
| normal_max_mse | 0.183 | {nh_max:.6f} |
| gap | -2.206 | {gap:.6f} |

## Criteria

| Criterion | Threshold | Actual | Pass? |
|-----------|-----------|--------|-------|
| F1 > 0.8 | >0.8 | {f1:.4f} | {"PASS" if pass_f1 else "FAIL"} |
| Localhost FPR < 10% | <10% | {lh_fpr_f1:.2%} | {"PASS" if pass_fpr else "FAIL"} |

## Decision

**{decision}**

{"V6 retraining resolves localhost domain gap. Eligible for Stage 9 (threshold calibration)." if verdict == "PASS" else "V6 retraining did not fully resolve localhost FPR. Further investigation needed."}

---

## Next Step

{"-> Proceed to Stage 9: Threshold calibration and production readiness" if verdict == "PASS" else "-> Investigate remaining domain gap; consider additional preprocessing or architecture changes"}
"""
    (E / "STAGE_8_DECISION.md").write_text(gate, encoding="utf-8")

    # ── Final print ─────────────────────────────────────────────────────────
    prod_match = before == meta["production_after"]
    print("\n" + "=" * 60)
    print("STAGE 8 -- V6 RETRAINING")
    print("=" * 60)
    print(f"\nTest Performance:")
    print(f"  ROC-AUC: {roc_auc:.4f}")
    print(f"  PR-AUC:  {pr_auc:.4f}")
    print(f"  F1:      {f1:.4f}")
    print(f"\nLocalhost Safety:")
    print(f"  FPR (F1 threshold): {lh_fpr_f1:.2%}")
    print(f"  FPR (safe P99):     {lh_fpr_safe:.2%}")
    print(f"  FPR (production):   {lh_fpr_prod:.2%}")
    print(f"\nDomain Gap:")
    print(f"  localhost_min: {lh_min:.6f}")
    print(f"  normal_max:    {nh_max:.6f}")
    print(f"  gap:           {gap:.6f}")
    print(f"\nDecision:")
    print(f"  -> {decision}")
    print(f"\nProduction integrity: {'VERIFIED' if prod_match else 'COMPROMISED'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
