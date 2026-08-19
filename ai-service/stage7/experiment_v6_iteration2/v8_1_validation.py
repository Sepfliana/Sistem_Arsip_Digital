"""
V8.1 Anomaly Validation
========================
Compute expected MSE for V8.1 anomalies using V7 model.
Compares with localhost to verify separation and moderate MSE.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import LabelEncoder

B = Path(__file__).resolve().parents[2]
V6 = B / "stage7" / "v6"
E = Path(__file__).resolve().parent
O = E / "retraining"
sys.path.insert(0, str(B))

SEED = 42

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


def vectorized_v6_preprocess(df: pd.DataFrame, status_fallback: str = "Berhasil") -> pd.DataFrame:
    c = pd.DataFrame()
    c["user_id"] = pd.to_numeric(df.get("user_id", 1), errors="coerce").fillna(1.0)
    raw_act = df.get("aksi", df.get("activity", "")).fillna("").astype(str).str.strip()
    reduced = raw_act.map(_ACTIVITY_REDUCTION)
    c["activity"] = reduced.fillna(raw_act.where(raw_act.isin(V6_ACTIVITY_CLASSES), "UNKNOWN"))
    raw_st = df.get("status", "").fillna("").astype(str).str.strip()
    c["status"] = raw_st.where(raw_st.isin(V6_STATUS_CLASSES), status_fallback)
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


def main():
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("=" * 60)
    print("V8.1 ANOMALY VALIDATION")
    print("=" * 60)

    # Load model
    print("\n[1] Load V7 model")
    from services.model_loader import VariationalAutoencoder
    ck = O / "vae_model_v7_experiment.pth"
    model = VariationalAutoencoder().to(device)
    model.load_state_dict(torch.load(ck, map_location=device, weights_only=False))
    model.eval()

    # Load pipeline
    with open(V6 / "preprocessing_pipeline.json", encoding="utf-8") as f:
        pipeline = json.load(f)
    encoders = {}
    for feat in ["activity", "status", "device", "ip_address"]:
        encoders[feat] = reconstruct_label_encoder(pipeline["encoders"][feat]["classes"])
    sc = V6Scaler(pipeline["scaler"]["mean"], pipeline["scaler"]["scale"])

    # Load V8.1 anomalies
    print("\n[2] Load V8.1 anomalies")
    v8_1 = pd.read_csv(V6 / "v8_1_anomaly_raw.csv")
    lh_eval = pd.read_csv(E / "localhost_eval_manifest.csv")
    val_norm = pd.read_csv(E / "validation_normal_manifest.csv")
    log(f"V8.1 anomalies: {len(v8_1)}")
    log(f"Localhost eval: {len(lh_eval)}")
    log(f"Val normal: {len(val_norm)}")

    # Encode
    print("\n[3] Encode")
    most_freq_status = "Berhasil"

    def encode_partition(df):
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

    Xv8 = encode_partition(v8_1)
    Xlh = encode_partition(lh_eval)
    Xvn = encode_partition(val_norm)
    log(f"V8.1 encoded: {Xv8.shape}")

    # Compute MSE
    print("\n[4] Compute MSE")
    def compute_mse(model, X):
        with torch.no_grad():
            q = torch.from_numpy(X).float().to(device)
            encoded = model.encoder(q)
            mu = model.mu(encoded)
            recon = model.decoder(mu)
            return (q - recon).pow(2).mean(dim=1).cpu().numpy()

    mse_v8 = compute_mse(model, Xv8)
    mse_lh = compute_mse(model, Xlh)
    mse_vn = compute_mse(model, Xvn)

    log(f"V8.1 MSE:    min={mse_v8.min():.6f}  mean={mse_v8.mean():.6f}  max={mse_v8.max():.6f}")
    log(f"Localhost:   min={mse_lh.min():.6f}  mean={mse_lh.mean():.6f}  max={mse_lh.max():.6f}")
    log(f"Val normal:  min={mse_vn.min():.6f}  mean={mse_vn.mean():.6f}  max={mse_vn.max():.6f}")

    # Per-type analysis
    print("\n[5] Per-type analysis")
    for atype in ["failed_offhours_access", "unknown_external_access", "failed_vm_access"]:
        mask = v8_1.anomaly_type == atype
        mse_sub = mse_v8[mask]
        log(f"  {atype}:")
        log(f"    count: {mask.sum()}")
        log(f"    MSE: min={mse_sub.min():.6f}  mean={mse_sub.mean():.6f}  max={mse_sub.max():.6f}")

    # Separation check
    print("\n[6] Separation check")
    lh_p95 = float(np.percentile(mse_lh, 95))
    lh_p99 = float(np.percentile(mse_lh, 99))
    lh_max = float(mse_lh.max())
    lh_mean = float(mse_lh.mean())
    v8_min = float(mse_v8.min())
    v8_p25 = float(np.percentile(mse_v8, 25))
    v8_mean = float(mse_v8.mean())
    v8_max = float(mse_v8.max())
    vn_max = float(mse_vn.max())

    overlap_count = int((mse_v8 < lh_p95).sum())
    overlap_pct = overlap_count / len(mse_v8) * 100

    mean_ratio = v8_mean / max(lh_mean, 1e-12)
    max_ratio = v8_max / max(lh_max, 1e-12)

    log(f"  Localhost P95: {lh_p95:.6f}")
    log(f"  Localhost mean: {lh_mean:.6f}")
    log(f"  Localhost max: {lh_max:.6f}")
    log(f"  V8.1 P25:      {v8_p25:.6f}")
    log(f"  V8.1 mean:     {v8_mean:.6f}")
    log(f"  V8.1 max:      {v8_max:.6f}")
    log(f"  Overlap (V8.1 < lh_p95): {overlap_count}/{len(mse_v8)} ({overlap_pct:.1f}%)")
    log(f"  Mean ratio (V8.1/lh): {mean_ratio:.2f}x")
    log(f"  Max ratio (V8.1/lh): {max_ratio:.2f}x")

    # Target metrics check
    print("\n[7] Target metrics check")
    target_p25_gt_p95 = v8_p25 > lh_p95
    target_mean_2x_5x = 2.0 <= mean_ratio <= 5.0
    target_max_lt_10x = max_ratio < 10.0

    log(f"  anomaly P25 > localhost P95: {v8_p25:.6f} > {lh_p95:.6f} = {'PASS' if target_p25_gt_p95 else 'FAIL'}")
    log(f"  anomaly mean = 2-5x localhost mean: {mean_ratio:.2f}x = {'PASS' if target_mean_2x_5x else 'FAIL'}")
    log(f"  anomaly max < 10x localhost max: {max_ratio:.2f}x = {'PASS' if target_max_lt_10x else 'FAIL'}")

    all_pass = target_p25_gt_p95 and target_mean_2x_5x and target_max_lt_10x

    # Save results
    print("\n[8] Save results")
    results = {
        "v8_1_anomaly_count": len(v8_1),
        "v8_1_mse_stats": {
            "min": round(v8_min, 6),
            "p25": round(v8_p25, 6),
            "mean": round(v8_mean, 6),
            "max": round(v8_max, 6),
        },
        "localhost_mse_stats": {
            "min": round(float(mse_lh.min()), 6),
            "mean": round(lh_mean, 6),
            "p95": round(lh_p95, 6),
            "p99": round(lh_p99, 6),
            "max": round(lh_max, 6),
        },
        "separation": {
            "overlap_count": overlap_count,
            "overlap_pct": round(overlap_pct, 2),
            "mean_ratio": round(mean_ratio, 2),
            "max_ratio": round(max_ratio, 2),
        },
        "target_metrics": {
            "p25_gt_p95": {"value": round(v8_p25, 6), "threshold": round(lh_p95, 6), "pass": target_p25_gt_p95},
            "mean_2x_5x": {"value": round(mean_ratio, 2), "range": "2.0-5.0", "pass": target_mean_2x_5x},
            "max_lt_10x": {"value": round(max_ratio, 2), "threshold": 10.0, "pass": target_max_lt_10x},
        },
        "all_pass": all_pass,
        "per_type_mse": {},
    }

    for atype in ["failed_offhours_access", "unknown_external_access", "failed_vm_access"]:
        mask = v8_1.anomaly_type == atype
        mse_sub = mse_v8[mask]
        results["per_type_mse"][atype] = {
            "count": int(mask.sum()),
            "min": round(float(mse_sub.min()), 6),
            "mean": round(float(mse_sub.mean()), 6),
            "max": round(float(mse_sub.max()), 6),
        }

    (E / "v8_1_validation_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Final print
    print("\n" + "=" * 60)
    print("V8.1 VALIDATION SUMMARY")
    print("=" * 60)
    print(f"\nANOMALY VS LOCALHOST GAP:")
    print(f"  V8.1 P25:   {v8_p25:.6f}")
    print(f"  lh P95:     {lh_p95:.6f}")
    print(f"  Gap:        {v8_p25 - lh_p95:.6f}")
    print(f"\nSEPARABILITY:")
    if target_p25_gt_p95:
        print(f"  PASS")
    else:
        print(f"  FAIL")
    print(f"\nEXTREMENESS CHECK:")
    if all_pass:
        print(f"  PASS")
    else:
        print(f"  FAIL")
    print(f"  mean ratio: {mean_ratio:.2f}x (target: 2-5x)")
    print(f"  max ratio:  {max_ratio:.2f}x (target: <10x)")
    print(f"\nOverlap: {overlap_pct:.1f}%")
    print("=" * 60)


def log(msg: str) -> None:
    print(f"  {msg}")


if __name__ == "__main__":
    main()
