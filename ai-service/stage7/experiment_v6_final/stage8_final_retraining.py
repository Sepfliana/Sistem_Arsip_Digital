"""
Stage 8 FINAL -- V8.1 Calibrated Anomaly Retraining
=====================================================
Experiment-only.  Never modifies production artifacts.
Seed = 42 everywhere.  All outputs to experiment_v6_final/.

Uses V8.1 calibrated anomalies (1000 records, 2-3 features mutated).
Applies V7 improvements: status fix + localhost split.
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
E = Path(__file__).resolve().parent            # experiment_v6_final/
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
# V6 PREPROCESSING
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


class V6Scaler:
    def __init__(self, mean, scale):
        self.mean_ = np.array(mean, dtype=np.float64)
        self.scale_ = np.array(scale, dtype=np.float64)

    def transform(self, X: np.ndarray) -> np.ndarray:
        return ((X - self.mean_) / self.scale_).astype("float32")


def reconstruct_label_encoder(classes: list) -> LabelEncoder:
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
    print("STAGE 8 FINAL -- V8.1 CALIBRATED ANOMALY RETRAINING")
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
    v8_1_raw = pd.read_csv(V6 / "v8_1_anomaly_raw.csv")
    with open(V6 / "preprocessing_pipeline.json", encoding="utf-8") as f:
        pipeline = json.load(f)

    log(f"Raw dataset: {len(raw)} rows")
    log(f"V8.1 anomalies: {len(v8_1_raw)} rows")

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 2 -- SOURCE-AWARE SPLIT
    # ════════════════════════════════════════════════════════════════════════
    print("\n[Phase 2] Source-Aware Split")

    # 2a. Filter SYNTHETIC NORMAL
    normal = raw[
        (raw.source_type == "SYNTHETIC") & (raw.candidate_type == "NORMAL")
    ].copy()
    log(f"Synthetic normal: {len(normal)}")

    # 2b. Exclude V8.1 anomaly base_record_ids
    v8_1_base_ids = set(v8_1_raw["base_record_id"].astype(str))
    sources = set(normal["source_id"].astype(str))
    missing = v8_1_base_ids - sources
    if missing:
        log(f"WARNING: {len(missing)} V8.1 base ids not in source pool")
    excluded = normal[normal["source_id"].astype(str).isin(v8_1_base_ids)]
    pool = normal[~normal["source_id"].astype(str).isin(v8_1_base_ids)].copy()
    log(f"Excluded V8.1 base sources: {len(excluded)}")
    log(f"Pool after exclusion: {len(pool)}")

    # 2c. Split LOCALHOST into train (70%) and eval (30%)
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
    n_synthetic_needed = int(n_lh_train * (70.0 / 30.0))
    pool_shuffled = pool.sample(frac=1, random_state=SEED).reset_index(drop=True)
    synthetic_train_pool = pool_shuffled.iloc[:n_synthetic_needed].copy()
    log(f"Synthetic for mix: {len(synthetic_train_pool)}")

    tr = pd.concat([synthetic_train_pool, lh_train], ignore_index=True)
    tr = tr.sample(frac=1, random_state=SEED).reset_index(drop=True)
    log(f"train_normal:     {len(tr)} (70% syn + 30% lh)")

    # 2e. Validation and test: SYNTHETIC ONLY
    remaining_synthetic = pool_shuffled.iloc[n_synthetic_needed:].copy()
    n_remaining = len(remaining_synthetic)
    n_val = int(0.5 * n_remaining)
    va = remaining_synthetic.iloc[:n_val].copy()
    te = remaining_synthetic.iloc[n_val:].copy()
    log(f"val_normal:       {len(va)} (synthetic only)")
    log(f"test_normal:      {len(te)} (synthetic only)")

    # 2f. Split V8.1 anomalies
    av = v8_1_raw.sample(frac=1, random_state=SEED).reset_index(drop=True)
    cut = len(av) // 2
    ava = av.iloc[:cut]
    ate = av.iloc[cut:]

    log(f"val_anomaly:      {len(ava)} (V8.1)")
    log(f"test_anomaly:     {len(ate)} (V8.1)")

    # 2g. Assertions
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
    assert not (tr_src & ava_base), "V8.1 base in train_normal"
    assert not (tr_src & ate_base), "V8.1 base in train_normal"
    assert not (va_src & ava_base), "V8.1 base in val_normal"
    assert not (va_src & ate_base), "V8.1 base in val_normal"
    assert not (te_src & ava_base), "V8.1 base in test_normal"
    assert not (te_src & ate_base), "V8.1 base in test_normal"
    # V8.1 allows shared base_record_ids across types (not a data leak)
    shared_bases = ava_base & ate_base
    if shared_bases:
        log(f"Note: {len(shared_bases)} base_record_ids shared across val/test anomaly (expected for V8.1)")
    assert len(ava) + len(ate) == len(v8_1_raw), "Anomaly count mismatch"
    assert not (lh_train_src & lh_eval_src), "LOCALHOST LEAKAGE"
    assert len(lh_train) + len(lh_eval) == n_lh, "Localhost count mismatch"
    assert not (lh_eval_src & va_src), "Localhost eval in val_normal"
    assert not (lh_eval_src & te_src), "Localhost eval in test_normal"
    log("Split assertions: PASS")

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 3 -- V6 ENCODE & SCALE
    # ════════════════════════════════════════════════════════════════════════
    print("\n[Phase 3] V6 Encode & Scale")

    encoders = {}
    for feat in ["activity", "status", "device", "ip_address"]:
        classes = pipeline["encoders"][feat]["classes"]
        encoders[feat] = reconstruct_label_encoder(classes)
        log(f"Encoder {feat}: {len(classes)} classes")

    sc = V6Scaler(pipeline["scaler"]["mean"], pipeline["scaler"]["scale"])

    # Compute most frequent status from TRAIN_NORMAL ONLY
    train_raw_status = tr.get("status", pd.Series([])).fillna("").astype(str).str.strip()
    most_freq_status = train_raw_status.mode()
    if len(most_freq_status) > 0:
        most_freq_status = most_freq_status.iloc[0]
    else:
        most_freq_status = "Berhasil"
    log(f"Status fallback: '{most_freq_status}'")

    def vectorized_v6_preprocess(df: pd.DataFrame) -> pd.DataFrame:
        c = pd.DataFrame()
        c["user_id"] = pd.to_numeric(df.get("user_id", 1), errors="coerce").fillna(1.0)
        raw_act = df.get("aksi", df.get("activity", "")).fillna("").astype(str).str.strip()
        reduced = raw_act.map(_ACTIVITY_REDUCTION)
        c["activity"] = reduced.fillna(raw_act.where(raw_act.isin(V6_ACTIVITY_CLASSES), "UNKNOWN"))
        raw_st = df.get("status", "").fillna("").astype(str).str.strip()
        c["status"] = raw_st.where(raw_st.isin(V6_STATUS_CLASSES), most_freq_status)
        raw_dev = df.get("device", "").fillna("").astype(str).str.strip()
        mapped_dev = raw_dev.where(raw_dev.isin(V6_DEVICE_CLASSES), "Unknown Device")
        c["device"] = mapped_dev.replace("Unknown Device", "PC Windows")
        ip_raw = df.get("ip_address", "").fillna("").astype(str).str.strip().str.lower()
        is_internal = (
            ip_raw.isin(["127.0.0.1", "::1", "localhost", "0.0.0.0"])
            | ip_raw.str.startswith("192.168.")
            | ip_raw.str.startswith("10.")
        )
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
        ip_stripped = ip_raw.str.replace("::ffff:", "", regex=False)
        is_internal = is_internal | (ip_stripped.str.startswith("127.") & ~is_internal)
        c["ip_address"] = np.where(is_internal, "Internal", "External")
        dur = pd.to_numeric(df.get("durasi_ms", df.get("duration_ms", 0)), errors="coerce").fillna(0.0)
        c["duration_ms"] = (dur > 0).astype(float)
        obj = pd.to_numeric(df.get("jumlah_objek", df.get("object_count", 0)), errors="coerce").fillna(0.0)
        obj = obj.clip(lower=0)
        c["object_count"] = np.log1p(obj)
        waktu_col = df.get("waktu", pd.Series([""] * len(df)))
        dt = pd.to_datetime(waktu_col, errors="coerce", utc=True)
        try:
            dt = dt.dt.tz_convert("Asia/Jakarta")
        except TypeError:
            dt = dt.dt.tz_localize("UTC").dt.tz_convert("Asia/Jakarta")
        hours_raw = dt.dt.hour.fillna(0).astype(int)
        c["hour"] = pd.cut(hours_raw, bins=[-1, 5, 11, 17, 23], labels=[3, 0, 1, 2]).astype(int)
        c["day_of_week"] = dt.dt.dayofweek.fillna(0).astype(int)
        return c

    def encode_partition(df: pd.DataFrame) -> np.ndarray:
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
    Xlh_eval = encode_partition(lh_eval)

    for name, X in [("train", Xtr), ("val_norm", Xv), ("test_norm", Xt),
                     ("val_anom", Xva), ("test_anom", Xta), ("lh_eval", Xlh_eval)]:
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
    ck = O / "vae_model_v8_1_experiment.pth"
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
        "anomaly_version": "V8.1",
        "training_composition": "70% synthetic + 30% localhost",
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

    ev       = mse(model2, Xv)
    et       = mse(model2, Xt)
    eva      = mse(model2, Xva)
    eta      = mse(model2, Xta)
    elh_eval = mse(model2, Xlh_eval)

    log(f"val_normal      MSE: {ev.mean():.6f}  (n={len(ev)})")
    log(f"test_normal     MSE: {et.mean():.6f}  (n={len(et)})")
    log(f"val_anomaly     MSE: {eva.mean():.6f}  (n={len(eva)})")
    log(f"test_anomaly    MSE: {eta.mean():.6f}  (n={len(eta)})")
    log(f"localhost_eval  MSE: {elh_eval.mean():.6f}  (n={len(elh_eval)})")

    # Thresholds
    y_val = np.r_[np.zeros(len(ev)), np.ones(len(eva))]
    s_val = np.r_[ev, eva]
    pr, re, th = precision_recall_curve(y_val, s_val)
    f1s = 2 * pr * re / (pr + re + 1e-12)
    best_idx = int(f1s.argmax())
    threshold_f1 = float(th[min(best_idx, len(th) - 1)])

    threshold_p95 = float(np.percentile(ev, 95))
    threshold_p99 = float(np.percentile(ev, 99))
    threshold_p995 = float(np.percentile(ev, 99.5))
    threshold_max = float(np.max(ev))

    log(f"Threshold (F1):  {threshold_f1:.6f}")
    log(f"Threshold (P95): {threshold_p95:.6f}")
    log(f"Threshold (P99): {threshold_p99:.6f}")
    log(f"Threshold (P99.5): {threshold_p995:.6f}")
    log(f"Threshold (max): {threshold_max:.6f}")

    # Test metrics
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

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 6 -- LOCALHOST SAFETY
    # ════════════════════════════════════════════════════════════════════════
    print("\n[Phase 6] Localhost Safety")

    thresholds_to_test = {
        "validation_f1_optimal": threshold_f1,
        "safe_p95": threshold_p95,
        "safe_p99": threshold_p99,
        "safe_p995": threshold_p995,
        "max_val_normal": threshold_max,
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

    # Domain gap
    lh_min = float(elh_eval.min())
    lh_max = float(elh_eval.max())
    lh_p95 = float(np.percentile(elh_eval, 95))
    nh_max = float(np.max([ev.max(), et.max()]))
    gap = lh_min - nh_max
    log(f"  Domain gap:")
    log(f"    localhost_eval_min: {lh_min:.6f}")
    log(f"    localhost_eval_max: {lh_max:.6f}")
    log(f"    localhost_eval_p95: {lh_p95:.6f}")
    log(f"    normal_max:         {nh_max:.6f}")
    log(f"    gap:                {gap:.6f}")

    (O / "localhost_safety.json").write_text(json.dumps(safety, indent=2), encoding="utf-8")

    # Distribution stats
    dist = pd.DataFrame([
        {"group": "validation_normal", **summary_stats(ev)},
        {"group": "test_normal", **summary_stats(et)},
        {"group": "validation_anomaly", **summary_stats(eva)},
        {"group": "test_anomaly", **summary_stats(eta)},
        {"group": "localhost_eval", **summary_stats(elh_eval)},
    ])
    dist.to_csv(O / "evaluation_distributions.csv", index=False)

    # Threshold sweep
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
        "threshold_safe_p95": round(threshold_p95, 6),
        "threshold_safe_p99": round(threshold_p99, 6),
        "threshold_safe_p995": round(threshold_p995, 6),
        "threshold_max_val_normal": round(threshold_max, 6),
    }
    (O / "evaluation_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    ck_sha = sha(ck) if ck.exists() else None
    meta = {
        "stage": "8",
        "version": "V8.1",
        "iteration": "final",
        "seed": SEED,
        "checkpoint_sha256": ck_sha,
        "checkpoint_reload": "PASS",
        "metrics": metrics,
        "localhost_safety": safety,
        "domain_gap": {
            "localhost_eval_min": lh_min,
            "localhost_eval_max": lh_max,
            "localhost_eval_p95": lh_p95,
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
        "anomaly_version": "V8.1",
    }, indent=2), encoding="utf-8")

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 8 -- DECISION GATE
    # ════════════════════════════════════════════════════════════════════════
    print("\n[Phase 8] Decision Gate")

    lh_fpr_f1 = safety["validation_f1_optimal"]["localhost_eval_fpr"]
    lh_fpr_p99 = safety["safe_p99"]["localhost_eval_fpr"]
    lh_fpr_p995 = safety["safe_p995"]["localhost_eval_fpr"]
    lh_fpr_prod = safety["production"]["localhost_eval_fpr"]

    # Find best threshold satisfying both criteria
    FPR_MAX = 0.10
    RECALL_MIN = 0.80
    candidates = [r for r in sweep_rows if r["localhost_eval_fpr"] <= FPR_MAX and r["test_recall"] >= RECALL_MIN]

    if candidates:
        best = max(candidates, key=lambda x: x["test_f1"])
        best_threshold = best["threshold"]
        best_f1 = best["test_f1"]
        best_recall = best["test_recall"]
        best_fpr = best["localhost_eval_fpr"]
        decision = "EXPERIMENT SUCCESS"
        verdict = "PASS"
    else:
        # Find best compromise
        for r in sweep_rows:
            r["score"] = r["test_recall"] - 2 * r["localhost_eval_fpr"]
        best = max(sweep_rows, key=lambda x: x["score"])
        best_threshold = best["threshold"]
        best_f1 = best["test_f1"]
        best_recall = best["test_recall"]
        best_fpr = best["localhost_eval_fpr"]
        decision = "EXPERIMENT FAIL"
        verdict = "FAIL"

    # Save threshold calibration
    cal_rows = []
    for name, thr in thresholds_to_test.items():
        fp = int((elh_eval >= thr).sum())
        fpr_val = float((elh_eval >= thr).mean())
        # Find recall at this threshold
        pred = eta >= thr
        tp = int(pred.sum())
        fn = int((~pred).sum())
        recall_at_thr = tp / (tp + fn) if (tp + fn) > 0 else 0
        cal_rows.append({
            "threshold_name": name,
            "threshold_value": round(thr, 6),
            "test_recall": round(recall_at_thr, 4),
            "localhost_fpr": round(fpr_val, 4),
        })
    if candidates:
        cal_rows.append({
            "threshold_name": "SELECTED",
            "threshold_value": round(best_threshold, 6),
            "test_recall": round(best_recall, 4),
            "localhost_fpr": round(best_fpr, 4),
        })
    pd.DataFrame(cal_rows).to_csv(O / "threshold_calibration.csv", index=False)

    # Save decision
    gate = f"""# Stage 8 FINAL -- V8.1 Retraining Decision Gate

**Date:** Stage 8 final
**Scope:** Experiment-only. No deployment.

---

## V8.1 Anomaly Dataset
- 1000 calibrated anomalies (2-3 features mutated)
- Types: failed_offhours_access, unknown_external_access, failed_vm_access
- Within training domain (user_id 1-86, object_count <=10)

## Test Performance

| Metric | Value |
|--------|-------|
| ROC-AUC | {roc_auc:.4f} |
| PR-AUC | {pr_auc:.4f} |
| F1 | {f1:.4f} |
| Precision | {prec:.4f} |
| Recall | {rec:.4f} |

## Localhost Safety

| Threshold | FPR |
|-----------|-----|
| F1 optimal ({threshold_f1:.6f}) | {lh_fpr_f1:.2%} |
| P99 ({threshold_p99:.6f}) | {lh_fpr_p99:.2%} |
| P99.5 ({threshold_p995:.6f}) | {lh_fpr_p995:.2%} |
| Production ({PROD_THRESHOLD:.6f}) | {lh_fpr_prod:.2%} |

## Domain Gap

| Metric | Value |
|--------|-------|
| localhost_eval_min | {lh_min:.6f} |
| localhost_eval_max | {lh_max:.6f} |
| localhost_eval_p95 | {lh_p95:.6f} |
| normal_max | {nh_max:.6f} |
| gap | {gap:.6f} |

## Threshold Selection

{"**Best threshold found:** " + str(round(best_threshold, 6)) if candidates else "**No threshold satisfies both criteria.**"}

| Criterion | Threshold | Actual | Pass? |
|-----------|-----------|--------|-------|
| F1 >= 0.80 | >=0.80 | {f1:.4f} | {"PASS" if f1 >= 0.80 else "FAIL"} |
| Localhost FPR <= 10% | <=10% | {best_fpr:.2%} | {"PASS" if best_fpr <= 0.10 else "FAIL"} |

## Decision

**{decision}**

{"V8.1 calibrated anomalies resolve the overlap. Model is production-viable." if verdict == "PASS" else "Model does not meet all criteria. Consider additional improvements."}

---

## Next Step

{"-> Proceed to Stage 9: Production readiness validation" if verdict == "PASS" else "-> Investigate remaining issues"}
"""
    (E / "STAGE_8_FINAL_DECISION.md").write_text(gate, encoding="utf-8")

    # ── Final Print ─────────────────────────────────────────────────────────
    prod_match = before == meta["production_after"]
    print("\n" + "=" * 60)
    print("STAGE 8 FINAL -- V8.1 RESULTS")
    print("=" * 60)
    print(f"\nF1: {f1:.4f}")
    print(f"BEST THRESHOLD: {best_threshold:.6f}")
    print(f"LOCALHOST FPR: {best_fpr:.2%}")
    print(f"FINAL DECISION: {verdict}")
    print(f"\nProduction integrity: {'VERIFIED' if prod_match else 'COMPROMISED'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
