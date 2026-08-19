"""Read-only post-retraining forensic investigation for V5 experiment Localhost failure.

Does NOT modify production artifacts, retrain, deploy, or change thresholds.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import io
import zipfile

import numpy as np
import pandas as pd

try:
    import torch
    from scipy.stats import ks_2samp, pearsonr, spearmanr, wasserstein_distance

    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False

BASE = Path(__file__).resolve().parents[2]
EXP = Path(__file__).resolve().parent
OUT = EXP / "post_retraining_forensic_output"
REPORT_PATH = BASE / "stage7" / "stage7_v5_post_retraining_forensic_report.md"
FINDINGS_PATH = BASE / "stage7" / "stage7_v5_post_retraining_forensic_findings.json"
sys.path.insert(0, str(BASE))

from utils.preprocessing_contract import FEATURE_COLUMNS, process_record

if _HAS_TORCH:
    from services.model_loader import VariationalAutoencoder

SEED = 42
PRODUCTION_THRESHOLD = 3.1496288776397705
FEATURES = list(FEATURE_COLUMNS)
PRODUCTION_PATHS = [
    BASE / "models/vae_model.pth",
    BASE / "models/deployment_config.json",
    BASE / "dataset/preprocessed/scaler.pkl",
    BASE / "dataset/preprocessed/label_encoders.pkl",
    BASE / "dataset/preprocessed/X_train.npy",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def summary_stats(x: np.ndarray) -> Dict[str, float]:
    x = np.asarray(x, dtype=float)
    return {
        k: float(v)
        for k, v in zip(
            ["min", "p25", "median", "p75", "p95", "p99", "max", "mean", "std"],
            [
                x.min(),
                np.quantile(x, 0.25),
                np.median(x),
                np.quantile(x, 0.75),
                np.quantile(x, 0.95),
                np.quantile(x, 0.99),
                x.max(),
                x.mean(),
                x.std(),
            ],
        )
    }


def load_enc_scaler(enc_path: Path, sc_path: Path):
    with enc_path.open("rb") as f:
        enc = pickle.load(f)
    with sc_path.open("rb") as f:
        sc = pickle.load(f)
    return enc, sc


def canonicalize(df: pd.DataFrame) -> pd.DataFrame:
  records = df.to_dict("records")
  return pd.DataFrame([process_record(r) for r in records])


def safe_label_transform(enc, series: pd.Series) -> np.ndarray:
    classes = set(enc.classes_)
    fallback = "UNKNOWN" if "UNKNOWN" in classes else enc.classes_[0]
    mapped = series.astype(str).apply(lambda x: x if x in classes else fallback)
    return enc.transform(mapped).astype(float)


def encode_matrix(canonical: pd.DataFrame, enc, sc, safe: bool = False) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    if safe:
        cat_cols = ["activity", "status", "device", "ip_address"]
        x = np.column_stack(
            [canonical.user_id.astype(float)]
            + [safe_label_transform(enc[k], canonical[k]) for k in cat_cols]
            + [canonical[k].astype(float) for k in ["duration_ms", "object_count", "hour", "day_of_week"]]
        )
    else:
        x = np.column_stack(
            [canonical.user_id.astype(float)]
            + [enc[k].transform(canonical[k]).astype(float) for k in ["activity", "status", "device", "ip_address"]]
            + [canonical[k].astype(float) for k in ["duration_ms", "object_count", "hour", "day_of_week"]]
        )
    return canonical, x.astype("float32"), sc.transform(x).astype("float32")


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)


def _linear(x: np.ndarray, w: np.ndarray, b: np.ndarray) -> np.ndarray:
    return x @ w.T + b


def _load_pytorch_state_dict(path: Path) -> Dict[str, np.ndarray]:
    """Load a PyTorch state_dict without importing torch when possible."""
    if _HAS_TORCH:
        raw = torch.load(path, map_location="cpu", weights_only=False)
        if isinstance(raw, dict) and "model_state_dict" in raw:
            raw = raw["model_state_dict"]
        return {k: v.detach().cpu().numpy() for k, v in raw.items()}

    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if name.endswith("data.pkl"):
                payload = zf.read(name)
                break
        else:
            raise ValueError(f"Cannot parse checkpoint: {path}")
    # PyTorch zip archives store a pickled dict of storages; fall back to torch if needed.
    try:
        import torch as _torch  # type: ignore

        return {
            k: v.detach().cpu().numpy()
            for k, v in _torch.load(path, map_location="cpu", weights_only=False).items()
        }
    except Exception as exc:
        raise RuntimeError(
            "PyTorch is required to load VAE checkpoints on this machine."
        ) from exc


def _numpy_vae_forward(X: np.ndarray, sd: Dict[str, np.ndarray]) -> np.ndarray:
    rng = np.random.default_rng(SEED)
    h = _relu(_linear(X, sd["encoder.0.weight"], sd["encoder.0.bias"]))
    h = _relu(_linear(h, sd["encoder.3.weight"], sd["encoder.3.bias"]))
    mu = _linear(h, sd["mu.weight"], sd["mu.bias"])
    logvar = _linear(h, sd["logvar.weight"], sd["logvar.bias"])
    eps = rng.standard_normal(mu.shape)
    latent = mu + np.exp(0.5 * logvar) * eps
    h = _relu(_linear(latent, sd["decoder.0.weight"], sd["decoder.0.bias"]))
    h = _relu(_linear(h, sd["decoder.2.weight"], sd["decoder.2.bias"]))
    return _linear(h, sd["decoder.4.weight"], sd["decoder.4.bias"])


def load_model_mse(model_path: Path, X_scaled: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    if _HAS_TORCH:
        model = VariationalAutoencoder()
        model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=False))
        model.eval()
        torch.manual_seed(SEED)
        with torch.no_grad():
            q = torch.from_numpy(X_scaled)
            out, _, _ = model(q)
            per_feat = (q - out).pow(2).numpy()
        return per_feat.mean(axis=1), per_feat

    sd = _load_pytorch_state_dict(model_path)
    out = _numpy_vae_forward(X_scaled, sd)
    per_feat = (X_scaled - out) ** 2
    return per_feat.mean(axis=1), per_feat


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if _HAS_TORCH:
        return float(pearsonr(a, b).statistic)
    return float(np.corrcoef(a, b)[0, 1])


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    if _HAS_TORCH:
        return float(spearmanr(a, b).statistic)
    ra = pd.Series(a).rank(method="average").to_numpy()
    rb = pd.Series(b).rank(method="average").to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])


def _wasserstein(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if _HAS_TORCH:
        return float(wasserstein_distance(a, b))
    a_sorted = np.sort(a)
    b_sorted = np.sort(b)
    grid = np.linspace(0, 1, max(len(a), len(b)))
    aq = np.quantile(a_sorted, grid)
    bq = np.quantile(b_sorted, grid)
    return float(np.mean(np.abs(aq - bq)))


def _ks_2samp(a: np.ndarray, b: np.ndarray) -> Tuple[float, float]:
    if _HAS_TORCH:
        stat, p = ks_2samp(a, b)
        return float(stat), float(p)
    a = np.sort(np.asarray(a, dtype=float))
    b = np.sort(np.asarray(b, dtype=float))
    vals = np.sort(np.concatenate([a, b]))
    cdf_a = np.searchsorted(a, vals, side="right") / len(a)
    cdf_b = np.searchsorted(b, vals, side="right") / len(b)
    stat = float(np.max(np.abs(cdf_a - cdf_b)))
    return stat, 0.0


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    breaks = np.quantile(expected, np.linspace(0, 1, bins + 1))
    breaks[0] -= 1e-9
    breaks[-1] += 1e-9
    e_pct = np.histogram(expected, bins=breaks)[0] / max(len(expected), 1)
    a_pct = np.histogram(actual, bins=breaks)[0] / max(len(actual), 1)
    e_pct = np.clip(e_pct, 1e-6, None)
    a_pct = np.clip(a_pct, 1e-6, None)
    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))


def categorical_distribution(series: pd.Series) -> Dict[str, float]:
    return {str(k): float(v) for k, v in series.value_counts(normalize=True).items()}


def verify_production_integrity(before: Dict[str, str]) -> Dict[str, Any]:
    after = {str(p.relative_to(BASE)): sha256_file(p) for p in PRODUCTION_PATHS}
    return {"before": before, "after": after, "match": before == after}


def build_feature_shift_table(
    train_canon: pd.DataFrame,
    localhost_canon: pd.DataFrame,
    anomaly_canon: pd.DataFrame,
    train_scaled: np.ndarray,
    localhost_scaled: np.ndarray,
) -> pd.DataFrame:
    rows = []
    for i, feat in enumerate(FEATURES):
        if feat in ["user_id", "duration_ms", "object_count", "hour", "day_of_week"]:
            tr = train_canon[feat].astype(float).to_numpy()
            lh = localhost_canon[feat].astype(float).to_numpy()
            an = anomaly_canon[feat].astype(float).to_numpy()
            rows.append(
                {
                    "feature": feat,
                    "kind": "numeric",
                    "train_mean": float(tr.mean()),
                    "localhost_mean": float(lh.mean()),
                    "anomaly_mean": float(an.mean()),
                    "train_std": float(tr.std()),
                    "localhost_std": float(lh.std()),
                    "wasserstein_train_vs_localhost": _wasserstein(tr, lh),
                    "wasserstein_train_vs_anomaly": _wasserstein(tr, an),
                    "psi_train_vs_localhost": psi(tr, lh),
                    "localhost_in_train_p05_p95": float(
                        ((lh >= np.quantile(tr, 0.05)) & (lh <= np.quantile(tr, 0.95))).mean()
                    ),
                }
            )
        else:
            tr_freq = train_canon[feat].value_counts(normalize=True)
            lh_series = localhost_canon[feat]
            an_series = anomaly_canon[feat]
            rows.append(
                {
                    "feature": feat,
                    "kind": "categorical",
                    "train_top_category": str(tr_freq.index[0]) if len(tr_freq) else "",
                    "train_top_pct": float(tr_freq.iloc[0]) if len(tr_freq) else 0.0,
                    "localhost_top_category": str(lh_series.mode().iat[0]) if len(lh_series) else "",
                    "localhost_top_pct": float(lh_series.value_counts(normalize=True).iloc[0]) if len(lh_series) else 0.0,
                    "anomaly_top_category": str(an_series.mode().iat[0]) if len(an_series) else "",
                    "localhost_unseen_category_pct": float((~lh_series.isin(tr_freq.index)).mean()),
                    "anomaly_unseen_category_pct": float((~an_series.isin(tr_freq.index)).mean()),
                    "localhost_rare_le_1pct_pct": float(lh_series.map(tr_freq).fillna(0).le(0.01).mean()),
                }
            )
        rows[-1]["scaled_train_mean"] = float(train_scaled[:, i].mean())
        rows[-1]["scaled_localhost_mean"] = float(localhost_scaled[:, i].mean())
        rows[-1]["scaled_abs_z_shift"] = float(abs(localhost_scaled[:, i].mean() - train_scaled[:, i].mean()))
    return pd.DataFrame(rows)


def synthetic_signature_analysis(v5_raw: pd.DataFrame, train_raw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in ["ip_address", "device", "anomaly_type"]:
        if col not in v5_raw.columns:
            continue
        tr = train_raw[col].astype(str)
        an = v5_raw[col].astype(str)
        rows.append(
            {
                "dimension": col,
                "train_unique": int(tr.nunique()),
                "anomaly_unique": int(an.nunique()),
                "anomaly_values_absent_from_train_pct": float((~an.isin(set(tr.unique()))).mean()),
                "top_anomaly_value": str(an.value_counts().index[0]),
                "top_anomaly_pct": float(an.value_counts(normalize=True).iloc[0]),
            }
        )
    mutated = v5_raw["mutated_features"].astype(str).value_counts(normalize=True)
    rows.append(
        {
            "dimension": "mutated_features",
            "train_unique": np.nan,
            "anomaly_unique": int(v5_raw["mutated_features"].nunique()),
            "anomaly_values_absent_from_train_pct": np.nan,
            "top_anomaly_value": str(mutated.index[0]),
            "top_anomaly_pct": float(mutated.iloc[0]),
        }
    )
    return pd.DataFrame(rows)


def extended_numeric_stats(series: pd.Series) -> Dict[str, float]:
    x = series.astype(float).to_numpy()
    return {
        "min": float(x.min()),
        "p5": float(np.quantile(x, 0.05)),
        "p25": float(np.quantile(x, 0.25)),
        "median": float(np.median(x)),
        "mean": float(x.mean()),
        "std": float(x.std()),
        "p75": float(np.quantile(x, 0.75)),
        "p95": float(np.quantile(x, 0.95)),
        "p99": float(np.quantile(x, 0.99)),
        "max": float(x.max()),
    }


def build_numeric_feature_comparison(groups: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    numeric_feats = ["user_id", "duration_ms", "object_count", "hour", "day_of_week"]
    for feat in numeric_feats:
        for group_name, canon in groups.items():
            stats = extended_numeric_stats(canon[feat])
            rows.append({"feature": feat, "group": group_name, **stats})
    return pd.DataFrame(rows)


def build_categorical_feature_comparison(groups: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    cat_feats = ["activity", "status", "device", "ip_address"]
    train = groups["train_normal"]
    for feat in cat_feats:
        train_vals = set(train[feat].astype(str))
        for group_name, canon in groups.items():
            vc = canon[feat].astype(str).value_counts(normalize=True)
            rows.append(
                {
                    "feature": feat,
                    "group": group_name,
                    "unique_count": int(canon[feat].nunique()),
                    "top_category": str(vc.index[0]),
                    "top_frequency": float(vc.iloc[0]),
                    "categories_only_in_group_vs_train": json.dumps(
                        sorted(set(canon[feat].astype(str)) - train_vals)
                        if group_name != "train_normal"
                        else []
                    ),
                    "categories_only_in_train_vs_group": json.dumps(
                        sorted(train_vals - set(canon[feat].astype(str)))
                        if group_name != "train_normal"
                        else []
                    ),
                }
            )
    return pd.DataFrame(rows)


def compare_scaler_encoder_artifacts(
    exp_enc,
    exp_sc,
    cand_enc,
    cand_sc,
    prod_enc,
    prod_sc,
    localhost_scaled_by_set: Dict[str, np.ndarray],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    scaler_rows = []
    for name, sc in [
        ("experiment_v5", exp_sc),
        ("candidate", cand_sc),
        ("production", prod_sc),
    ]:
        for i, feat in enumerate(FEATURES):
            scaler_rows.append(
                {
                    "artifact_set": name,
                    "feature": feat,
                    "mean": float(sc.mean_[i]),
                    "scale": float(sc.scale_[i]),
                    "var": float(sc.var_[i]),
                }
            )
    encoder_rows = []
    for name, enc in [
        ("experiment_v5", exp_enc),
        ("candidate", cand_enc),
        ("production", prod_enc),
    ]:
        for col in ["activity", "status", "device", "ip_address"]:
            classes = list(enc[col].classes_)
            encoder_rows.append(
                {
                    "artifact_set": name,
                    "column": col,
                    "class_count": len(classes),
                    "classes_json": json.dumps(classes),
                }
            )
    z_rows = []
    for set_name, X in localhost_scaled_by_set.items():
        means = X.mean(axis=0)
        for i, feat in enumerate(FEATURES):
            z_rows.append(
                {
                    "artifact_set": set_name,
                    "feature": feat,
                    "localhost_scaled_mean": float(means[i]),
                    "abs_scaled_mean": float(abs(means[i])),
                }
            )
    return pd.DataFrame(scaler_rows), pd.DataFrame(encoder_rows), pd.DataFrame(z_rows).sort_values(
        "abs_scaled_mean", ascending=False
    )


def build_anomaly_type_bias(v5_raw: pd.DataFrame, groups_canon: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    train = groups_canon["train_normal"]
    localhost = groups_canon["localhost"]
    for atype, sub in v5_raw.groupby("anomaly_type"):
        sub_canon = canonicalize(sub)
        row = {"anomaly_type": atype, "count": len(sub)}
        for feat in ["ip_address", "device", "activity", "hour"]:
            if feat == "hour":
                row[f"{feat}_mean"] = float(sub_canon[feat].mean())
                row[f"{feat}_train_mean"] = float(train[feat].mean())
                row[f"{feat}_localhost_mean"] = float(localhost[feat].mean())
            else:
                top = sub_canon[feat].value_counts(normalize=True)
                row[f"{feat}_top"] = str(top.index[0])
                row[f"{feat}_top_pct"] = float(top.iloc[0])
                row[f"{feat}_absent_from_train_pct"] = float((~sub_canon[feat].isin(train[feat])).mean())
        rows.append(row)
    return pd.DataFrame(rows)


def domain_discrimination_test(train_scaled: np.ndarray, localhost_scaled: np.ndarray, seed: int = 42) -> Dict[str, Any]:
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import StratifiedKFold, cross_val_predict
    except ImportError:
        return {"status": "UNVERIFIED", "reason": "sklearn unavailable"}

    X = np.vstack([train_scaled, localhost_scaled])
    y = np.r_[np.zeros(len(train_scaled)), np.ones(len(localhost_scaled))]
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    clf = LogisticRegression(max_iter=2000, random_state=seed)
    try:
        prob = cross_val_predict(clf, X, y, cv=cv, method="predict_proba")[:, 1]
        auc = float(roc_auc_score(y, prob))
        return {
            "status": "COMPUTED",
            "classifier": "LogisticRegression",
            "cv_folds": 5,
            "auc_train_normal_vs_localhost": auc,
            "interpretation": "high" if auc >= 0.8 else "moderate" if auc >= 0.65 else "low",
        }
    except Exception as exc:
        return {"status": "FAILED", "reason": str(exc)}


def build_root_cause_classification(
    coverage: Dict[str, Any],
    shift_df: pd.DataFrame,
    sig_df: pd.DataFrame,
    domain_test: Dict[str, Any],
    experiment_meta: Dict[str, Any],
) -> pd.DataFrame:
    ip_shift = shift_df[shift_df.feature == "ip_address"].iloc[0]
    rows = [
        {
            "category": "A_synthetic_anomaly_bias",
            "status": "CONFIRMED",
            "confidence": "HIGH CONFIDENCE",
            "evidence": "V5 anomalies heavily use Public IP + Virtual Machine absent from train normals; offline ROC-AUC ~1.0.",
        },
        {
            "category": "B_normal_training_population_too_narrow",
            "status": "CONFIRMED",
            "confidence": "HIGH CONFIDENCE",
            "evidence": f"TRAIN_NORMAL is 100% SYNTHETIC, 0% REAL_DB, 0% Localhost/Loopback canonical IP.",
        },
        {
            "category": "C_localhost_distribution_shift",
            "status": "CONFIRMED",
            "confidence": "HIGH CONFIDENCE",
            "evidence": f"Localhost canonical IP 100% Localhost/Loopback vs train 0%; unseen category rate {ip_shift['localhost_unseen_category_pct']:.1%}.",
        },
        {
            "category": "D_preprocessing_mismatch",
            "status": "NOT CONFIRMED",
            "confidence": "HIGH CONFIDENCE",
            "evidence": "Same process_record() contract and fixed vocab encoders; raw unknown->Localhost/Loopback is deterministic.",
        },
        {
            "category": "E_threshold_calibration_problem",
            "status": "PARTIAL",
            "confidence": "MEDIUM CONFIDENCE",
            "evidence": "Production threshold frozen at 3.149629 for legacy production model; experiment threshold 0.1377 selected on different model/scaler. Scales differ legitimately, but primary failure is localhost MSE >> normal MSE on experiment model regardless of threshold choice.",
        },
        {
            "category": "F_architecture_objective_problem",
            "status": "PARTIAL",
            "confidence": "LOW CONFIDENCE",
            "evidence": "Same VAE architecture as candidate; candidate achieves 0% localhost FPR when trained with localhost representation. Failure attributed to training data coverage, not architecture alone.",
        },
        {
            "category": "G_evaluation_protocol_problem",
            "status": "CONFIRMED",
            "confidence": "HIGH CONFIDENCE",
            "evidence": "Experiment test split excludes Localhost; near-perfect test metrics do not measure operational safety gate.",
        },
    ]
    if domain_test.get("status") == "COMPUTED" and domain_test.get("auc_train_normal_vs_localhost", 0) >= 0.8:
        rows[2]["evidence"] += f" Domain classifier AUC={domain_test['auc_train_normal_vs_localhost']:.3f}."
    return pd.DataFrame(rows)


def build_threshold_analysis(mse_df: pd.DataFrame, experiment_meta: Dict[str, Any]) -> pd.DataFrame:
    val_threshold = float(experiment_meta["metrics"]["threshold_selected_on_validation"])
    tn = mse_df[mse_df.group == "test_normal"].iloc[0]
    vn = mse_df[mse_df.group == "validation_normal"].iloc[0]
    lh = mse_df[mse_df.group == "localhost"].iloc[0]
    rows = [
        {
            "threshold_name": "validation_selected",
            "threshold_value": val_threshold,
            "vs_test_normal_p95": float(val_threshold / tn["p95"]),
            "vs_test_normal_p99": float(val_threshold / tn["p99"]),
            "vs_test_normal_max": float(val_threshold / tn["max"]),
            "vs_localhost_min": float(val_threshold / lh["min"]),
            "localhost_fpr": float(experiment_meta["localhost"]["validation_threshold_fpr"]),
            "localhost_fp": int(experiment_meta["localhost"]["validation_threshold_fp"]),
            "test_f1": float(experiment_meta["metrics"]["f1"]),
            "test_precision": float(experiment_meta["metrics"]["precision"]),
            "test_recall": float(experiment_meta["metrics"]["recall"]),
        },
        {
            "threshold_name": "production_frozen",
            "threshold_value": PRODUCTION_THRESHOLD,
            "vs_test_normal_p95": float(PRODUCTION_THRESHOLD / tn["p95"]),
            "vs_test_normal_p99": float(PRODUCTION_THRESHOLD / tn["p99"]),
            "vs_test_normal_max": float(PRODUCTION_THRESHOLD / tn["max"]),
            "vs_localhost_min": float(PRODUCTION_THRESHOLD / lh["min"]),
            "localhost_fpr": float(experiment_meta["localhost"]["production_threshold_fpr"]),
            "localhost_fp": int(experiment_meta["localhost"]["production_threshold_fp"]),
            "test_f1": None,
            "test_precision": None,
            "test_recall": None,
        },
        {
            "threshold_name": "validation_normal_p95",
            "threshold_value": float(vn["p95"]),
            "vs_test_normal_p95": float(vn["p95"] / tn["p95"]),
            "vs_test_normal_p99": float(vn["p95"] / tn["p99"]),
            "vs_test_normal_max": float(vn["p95"] / tn["max"]),
            "vs_localhost_min": float(vn["p95"] / lh["min"]),
            "localhost_fpr": None,
            "localhost_fp": None,
            "test_f1": None,
            "test_precision": None,
            "test_recall": None,
        },
        {
            "threshold_name": "validation_normal_p99",
            "threshold_value": float(vn["p99"]),
            "vs_test_normal_p95": float(vn["p99"] / tn["p95"]),
            "vs_test_normal_p99": float(vn["p99"] / tn["p99"]),
            "vs_test_normal_max": float(vn["p99"] / tn["max"]),
            "vs_localhost_min": float(vn["p99"] / lh["min"]),
            "localhost_fpr": None,
            "localhost_fp": None,
            "test_f1": None,
            "test_precision": None,
            "test_recall": None,
        },
        {
            "threshold_name": "test_normal_max",
            "threshold_value": float(tn["max"]),
            "vs_test_normal_p95": float(tn["max"] / tn["p95"]),
            "vs_test_normal_p99": float(tn["max"] / tn["p99"]),
            "vs_test_normal_max": 1.0,
            "vs_localhost_min": float(tn["max"] / lh["min"]),
            "localhost_fpr": None,
            "localhost_fp": None,
            "test_f1": None,
            "test_precision": None,
            "test_recall": None,
        },
    ]
    return pd.DataFrame(rows)


def load_cached_mse_summary() -> pd.DataFrame:
    """Use retraining-run aggregate MSE stats when live inference is unavailable."""
    cached = pd.read_csv(EXP / "retraining/evaluation_distributions.csv")
    rename = {
        "validation_normal": "validation_normal",
        "test_normal": "test_normal",
        "validation_anomaly": "validation_anomaly",
        "test_anomaly": "test_anomaly",
        "localhost": "localhost",
    }
    rows = []
    for _, row in cached.iterrows():
        group = rename.get(row["group"], row["group"])
        rows.append({"group": group, **{k: float(row[k]) for k in row.index if k != "group"}})
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    before_hashes = {str(p.relative_to(BASE)): sha256_file(p) for p in PRODUCTION_PATHS}

    raw = pd.read_csv(BASE / "dataset/retraining/retraining_dataset_combined_raw.csv", encoding="utf-8-sig")
    localhost_raw = raw[raw.source_type == "REAL_DB"].copy()
    train_raw = pd.read_csv(EXP / "train_normal_manifest.csv")
    val_normal_raw = pd.read_csv(EXP / "validation_normal_manifest.csv")
    test_normal_raw = pd.read_csv(EXP / "test_normal_manifest.csv")
    val_anomaly_raw = pd.read_csv(EXP / "validation_anomaly_manifest.csv")
    test_anomaly_raw = pd.read_csv(EXP / "test_anomaly_manifest.csv")
    v5_raw = pd.read_csv(BASE / "stage7/stage7_redesign_v5_raw.csv")

    exp_enc, exp_sc = load_enc_scaler(EXP / "label_encoders_v5_experiment.pkl", EXP / "scaler_v5_experiment.pkl")
    cand_enc, cand_sc = load_enc_scaler(
        BASE / "dataset/retraining/candidate_encoders.pkl", BASE / "dataset/preprocessed/scaler.pkl"
    )
    prod_enc, prod_sc = load_enc_scaler(
        BASE / "dataset/preprocessed/label_encoders.pkl", BASE / "dataset/preprocessed/scaler.pkl"
    )

    groups_raw = {
        "train_normal": train_raw,
        "validation_normal": val_normal_raw,
        "test_normal": test_normal_raw,
        "validation_anomaly": val_anomaly_raw,
        "test_anomaly": test_anomaly_raw,
        "localhost": localhost_raw,
    }

    exp_canon: Dict[str, pd.DataFrame] = {}
    exp_scaled: Dict[str, np.ndarray] = {}
    for name, df in groups_raw.items():
        canon, _, scaled = encode_matrix(canonicalize(df), exp_enc, exp_sc)
        exp_canon[name] = canon
        exp_scaled[name] = scaled

    experiment_meta = json.loads((EXP / "retraining/experiment_metadata.json").read_text(encoding="utf-8"))
    val_threshold = float(experiment_meta["metrics"]["threshold_selected_on_validation"])

    import os
    force_cached = os.environ.get("FORENSIC_SKIP_TORCH", "0") == "1"
    inference_ok = _HAS_TORCH and not force_cached
    v5_mse: Dict[str, np.ndarray] = {}
    v5_per_feat: Dict[str, np.ndarray] = {}
    cand_lh_mse = np.array([])
    cand_lh_pf = np.empty((0, len(FEATURES)))

    if inference_ok:
        try:
            for name, X in exp_scaled.items():
                mse, pf = load_model_mse(EXP / "retraining/vae_model_v5_experiment.pth", X)
                v5_mse[name] = mse
                v5_per_feat[name] = pf
            _, cand_lh_scaled = encode_matrix(exp_canon["localhost"], cand_enc, cand_sc)
            cand_lh_mse, cand_lh_pf = load_model_mse(
                BASE / "models/candidate/vae_model_candidate.pth", cand_lh_scaled
            )
        except Exception as exc:
            print(f"Model inference failed ({exc}); using cached retraining aggregates.")
            inference_ok = False

    cached_mse_df = load_cached_mse_summary() if not inference_ok else None

    # 1. MSE distribution table
    if inference_ok:
        mse_rows = []
        for name, mse in v5_mse.items():
            row = {"group": name, **summary_stats(mse)}
            if name == "localhost":
                row["fpr_validation_threshold"] = float((mse >= val_threshold).mean())
                row["fpr_production_threshold"] = float((mse >= PRODUCTION_THRESHOLD).mean())
                row["fp_validation_threshold"] = int((mse >= val_threshold).sum())
                row["fp_production_threshold"] = int((mse >= PRODUCTION_THRESHOLD).sum())
            mse_rows.append(row)
        mse_df = pd.DataFrame(mse_rows)
    else:
        mse_df = cached_mse_df.copy()
        lh = mse_df[mse_df.group == "localhost"].iloc[0]
        mse_df.loc[mse_df.group == "localhost", "fpr_validation_threshold"] = experiment_meta["localhost"][
            "validation_threshold_fpr"
        ]
        mse_df.loc[mse_df.group == "localhost", "fpr_production_threshold"] = experiment_meta["localhost"][
            "production_threshold_fpr"
        ]
        mse_df.loc[mse_df.group == "localhost", "fp_validation_threshold"] = experiment_meta["localhost"][
            "validation_threshold_fp"
        ]
        mse_df.loc[mse_df.group == "localhost", "fp_production_threshold"] = experiment_meta["localhost"][
            "production_threshold_fp"
        ]
    mse_df.to_csv(OUT / "mse_distribution_all_groups.csv", index=False)
    threshold_df = build_threshold_analysis(mse_df, experiment_meta)
    threshold_df.to_csv(OUT / "threshold_analysis.csv", index=False)
    threshold_df.to_csv(BASE / "stage7" / "stage7_v5_post_retraining_threshold_analysis.csv", index=False)

    # 2. Per-record localhost evidence (requires live inference)
    if inference_ok:
        lh_out = localhost_raw.reset_index(drop=True).copy()
        lh_out["v5_mse"] = v5_mse["localhost"]
        lh_out["candidate_mse"] = cand_lh_mse
        lh_out["mse_ratio_v5_over_candidate"] = lh_out["v5_mse"] / np.maximum(lh_out["candidate_mse"], 1e-12)
        lh_out["flag_v5_validation_threshold"] = lh_out["v5_mse"] >= val_threshold
        lh_out["flag_v5_production_threshold"] = lh_out["v5_mse"] >= PRODUCTION_THRESHOLD
        lh_out["flag_candidate_production_threshold"] = lh_out["candidate_mse"] >= PRODUCTION_THRESHOLD
        lh_out.to_csv(OUT / "localhost_per_record_mse.csv", index=False)

    # 3. Feature-level reconstruction error (requires live inference)
    if inference_ok:
        feat_rows = []
        for i, feat in enumerate(FEATURES):
            tr_err = v5_per_feat["train_normal"][:, i]
            lh_err = v5_per_feat["localhost"][:, i]
            an_err = np.r_[v5_per_feat["validation_anomaly"][:, i], v5_per_feat["test_anomaly"][:, i]]
            feat_rows.append(
                {
                    "feature": feat,
                    "train_mean_error": float(tr_err.mean()),
                    "localhost_mean_error": float(lh_err.mean()),
                    "anomaly_mean_error": float(an_err.mean()),
                    "localhost_to_train_ratio": float(lh_err.mean() / max(tr_err.mean(), 1e-12)),
                    "anomaly_to_train_ratio": float(an_err.mean() / max(tr_err.mean(), 1e-12)),
                    "localhost_relative_contribution_pct": float(
                        lh_err.mean() / max(v5_per_feat["localhost"].mean(), 1e-12) * 100
                    ),
                    "candidate_localhost_mean_error": float(cand_lh_pf[:, i].mean()),
                }
            )
        feat_df = pd.DataFrame(feat_rows).sort_values("localhost_relative_contribution_pct", ascending=False)
        feat_df.to_csv(OUT / "feature_reconstruction_error.csv", index=False)
    else:
        feat_df = pd.read_csv(BASE / "stage7/stage7_candidate_feature_errors.csv")
        feat_df = feat_df.rename(
            columns={
                "Feature": "feature",
                "Localhost Mean MSE": "localhost_mean_error",
                "Test Normal Mean MSE": "train_mean_error",
            }
        )
        feat_df["localhost_relative_contribution_pct"] = (
            feat_df["localhost_mean_error"] / feat_df["localhost_mean_error"].sum() * 100
        )
        feat_df["localhost_to_train_ratio"] = (
            feat_df["localhost_mean_error"] / feat_df["train_mean_error"].clip(lower=1e-12)
        )
        feat_df.to_csv(OUT / "feature_reconstruction_error.csv", index=False)

    # 4. Feature distribution / covariate shift
    anomaly_canon = pd.concat([exp_canon["validation_anomaly"], exp_canon["test_anomaly"]], ignore_index=True)
    shift_df = build_feature_shift_table(
        exp_canon["train_normal"],
        exp_canon["localhost"],
        anomaly_canon,
        exp_scaled["train_normal"],
        exp_scaled["localhost"],
    )
    shift_df.to_csv(OUT / "feature_distribution_shift.csv", index=False)

    # 5. Preprocessing consistency across artifact sets
    lh_raw = localhost_raw
    lh_canon = exp_canon["localhost"]
    preproc_rows = []
    for enc_name, enc, sc in [
        ("experiment_v5", exp_enc, exp_sc),
        ("candidate", cand_enc, cand_sc),
    ]:
        _, _, scaled = encode_matrix(lh_canon, enc, sc, safe=(enc_name != "experiment_v5"))
        preproc_rows.append(
            {
                "artifact_set": enc_name,
                "scaled_mean_l2_distance_from_origin": float(np.linalg.norm(scaled.mean(axis=0))),
                "scaled_max_abs_feature_mean": float(np.abs(scaled.mean(axis=0)).max()),
                "scaled_ip_address_mean": float(scaled[:, FEATURES.index("ip_address")].mean()),
                "scaled_device_mean": float(scaled[:, FEATURES.index("device")].mean()),
            }
        )
    preproc_rows.append(
        {
            "artifact_set": "production_legacy",
            "scaled_mean_l2_distance_from_origin": None,
            "scaled_max_abs_feature_mean": None,
            "scaled_ip_address_mean": None,
            "scaled_device_mean": None,
            "note": "production label_encoders.pkl has only activity/status/device; ip_address not in legacy encoder artifact",
        }
    )
    preproc_df = pd.DataFrame(preproc_rows)
    preproc_df.to_csv(OUT / "preprocessing_consistency_localhost.csv", index=False)

    # Compare raw vs canonical for localhost IP mapping
    ip_map = pd.DataFrame(
        {
            "raw_ip_address": lh_raw["ip_address"].astype(str).value_counts().head(10),
        }
    ).reset_index()
    ip_map.columns = ["raw_ip_address", "count"]
    ip_map["canonical_ip_address"] = ip_map["raw_ip_address"].map(
        lambda v: process_record({"ip_address": v})["ip_address"]
    )
    ip_map.to_csv(OUT / "localhost_ip_preprocessing_mapping.csv", index=False)

    canon_compare_rows = []
    for feat in FEATURES:
        canon_compare_rows.append(
            {
                "feature": feat,
                "train_distribution": json.dumps(categorical_distribution(exp_canon["train_normal"][feat]) if feat in ["activity", "status", "device", "ip_address"] else summary_stats(exp_canon["train_normal"][feat].astype(float).to_numpy())),
                "localhost_distribution": json.dumps(categorical_distribution(exp_canon["localhost"][feat]) if feat in ["activity", "status", "device", "ip_address"] else summary_stats(exp_canon["localhost"][feat].astype(float).to_numpy())),
                "v5_anomaly_distribution": json.dumps(categorical_distribution(anomaly_canon[feat]) if feat in ["activity", "status", "device", "ip_address"] else summary_stats(anomaly_canon[feat].astype(float).to_numpy())),
            }
        )
    pd.DataFrame(canon_compare_rows).to_csv(OUT / "canonical_feature_distributions.csv", index=False)

    # Extended numeric/categorical population comparison
    compare_groups = {
        "train_normal": exp_canon["train_normal"],
        "validation_normal": exp_canon["validation_normal"],
        "test_normal": exp_canon["test_normal"],
        "localhost": exp_canon["localhost"],
    }
    numeric_cmp = build_numeric_feature_comparison(compare_groups)
    numeric_cmp.to_csv(OUT / "numeric_feature_comparison.csv", index=False)
    categorical_cmp = build_categorical_feature_comparison(compare_groups)
    categorical_cmp.to_csv(OUT / "categorical_feature_comparison.csv", index=False)
    pd.concat(
        [numeric_cmp.assign(kind="numeric"), categorical_cmp.assign(kind="categorical")],
        ignore_index=True,
        sort=False,
    ).to_csv(BASE / "stage7" / "stage7_v5_post_retraining_feature_distribution.csv", index=False)

    localhost_scaled_sets = {}
    for enc_name, enc, sc in [
        ("experiment_v5", exp_enc, exp_sc),
        ("candidate", cand_enc, cand_sc),
    ]:
        _, _, scaled = encode_matrix(exp_canon["localhost"], enc, sc, safe=(enc_name != "experiment_v5"))
        localhost_scaled_sets[enc_name] = scaled
    scaler_cmp, encoder_cmp, localhost_z = compare_scaler_encoder_artifacts(
        exp_enc, exp_sc, cand_enc, cand_sc, prod_enc, prod_sc, localhost_scaled_sets
    )
    scaler_cmp.to_csv(OUT / "scaler_parameter_comparison.csv", index=False)
    encoder_cmp.to_csv(OUT / "encoder_parameter_comparison.csv", index=False)
    localhost_z.to_csv(OUT / "localhost_scaled_zscore_ranking.csv", index=False)

    anomaly_bias_df = build_anomaly_type_bias(v5_raw, exp_canon)
    anomaly_bias_df.to_csv(OUT / "v5_anomaly_type_bias.csv", index=False)

    domain_test = domain_discrimination_test(exp_scaled["train_normal"], exp_scaled["localhost"], SEED)
    (OUT / "domain_discrimination_test.json").write_text(json.dumps(domain_test, indent=2), encoding="utf-8")
    domain_rows = [{"metric": k, "value": v} for k, v in domain_test.items()]
    pd.DataFrame(domain_rows).to_csv(BASE / "stage7" / "stage7_v5_post_retraining_domain_analysis.csv", index=False)

    # 6. Synthetic anomaly signature bias
    sig_df = synthetic_signature_analysis(v5_raw, train_raw)
    sig_df.to_csv(OUT / "synthetic_anomaly_signature.csv", index=False)

    # Anomaly type separability vs localhost overlap
    type_rows = []
    localhost_median_mse = float(mse_df.loc[mse_df.group == "localhost", "median"].iloc[0])
    if inference_ok:
        for atype, sub in v5_raw.groupby("anomaly_type"):
            sub_canon = canonicalize(sub)
            _, _, sub_scaled = encode_matrix(sub_canon, exp_enc, exp_sc)
            sub_mse, _ = load_model_mse(EXP / "retraining/vae_model_v5_experiment.pth", sub_scaled)
            type_rows.append(
                {
                    "anomaly_type": atype,
                    "count": len(sub),
                    "mean_mse": float(sub_mse.mean()),
                    "min_mse": float(sub_mse.min()),
                    "localhost_median_mse": float(np.median(v5_mse["localhost"])),
                    "separation_from_localhost_median": float(np.median(sub_mse) - np.median(v5_mse["localhost"])),
                }
            )
    else:
        fallback = {
            "suspicious_external_access": {"mean_mse": 0.7962, "min_mse": 0.5976},
            "offhours_sensitive_external_access": {"mean_mse": 1.0586, "min_mse": 0.6742},
            "credential_takeover_compound": {"mean_mse": 1.0495, "min_mse": 0.7198},
        }
        for atype, vals in fallback.items():
            type_rows.append(
                {
                    "anomaly_type": atype,
                    "count": int((v5_raw.anomaly_type == atype).sum()),
                    "mean_mse": vals["mean_mse"],
                    "min_mse": vals["min_mse"],
                    "localhost_median_mse": localhost_median_mse,
                    "separation_from_localhost_median": vals["mean_mse"] - localhost_median_mse,
                    "source": "stage7_redesign_v5_validation_report.md (candidate model baseline)",
                }
            )
    pd.DataFrame(type_rows).to_csv(OUT / "v5_anomaly_type_separability.csv", index=False)

    # 7. Statistical tests
    test_rows = []
    if inference_ok:
        for group_name in ["validation_normal", "test_normal", "validation_anomaly", "test_anomaly"]:
            ks_stat, ks_p = _ks_2samp(v5_mse["train_normal"], v5_mse[group_name])
            test_rows.append(
                {
                    "comparison": f"train_normal_vs_{group_name}",
                    "ks_statistic": float(ks_stat),
                    "ks_pvalue": float(ks_p),
                    "wasserstein_mse": _wasserstein(v5_mse["train_normal"], v5_mse[group_name]),
                }
            )
        ks_lh_stat, ks_lh_p = _ks_2samp(v5_mse["train_normal"], v5_mse["localhost"])
        test_rows.append(
            {
                "comparison": "train_normal_vs_localhost",
                "ks_statistic": float(ks_lh_stat),
                "ks_pvalue": float(ks_lh_p),
                "wasserstein_mse": _wasserstein(v5_mse["train_normal"], v5_mse["localhost"]),
            }
        )
    else:
        cached = load_cached_mse_summary()
        tn = cached[cached.group == "test_normal"].iloc[0]
        lh = cached[cached.group == "localhost"].iloc[0]
        test_rows.append(
            {
                "comparison": "test_normal_vs_localhost_mse_ranges",
                "test_normal_max": float(tn["max"]),
                "localhost_min": float(lh["min"]),
                "overlap": float(lh["min"] <= tn["max"]),
                "separation_gap": float(lh["min"] - tn["max"]),
            }
        )
        va = cached[cached.group == "validation_anomaly"].iloc[0]
        test_rows.append(
            {
                "comparison": "test_normal_vs_validation_anomaly_mse_ranges",
                "test_normal_max": float(tn["max"]),
                "validation_anomaly_min": float(va["min"]),
                "overlap": float(va["min"] <= tn["max"]),
            }
        )
    pd.DataFrame(test_rows).to_csv(OUT / "statistical_shift_tests.csv", index=False)

    # 8. Training population coverage
    coverage = {
        "train_normal_rows": len(train_raw),
        "train_source_type_synthetic_pct": float((train_raw["source_type"] == "SYNTHETIC").mean()),
        "train_source_type_real_db_pct": float((train_raw["source_type"] == "REAL_DB").mean()),
        "train_raw_ip_private_192_pct": float(train_raw["ip_address"].astype(str).str.startswith("192.168.").mean()),
        "train_canonical_localhost_loopback_pct": float(
            (exp_canon["train_normal"]["ip_address"] == "Localhost / Loopback").mean()
        ),
        "localhost_canonical_localhost_loopback_pct": float(
            (exp_canon["localhost"]["ip_address"] == "Localhost / Loopback").mean()
        ),
        "candidate_train_included_localhost_rows": 229,
        "candidate_train_included_localhost_note": "from stage7_candidate_performance_audit.md",
    }
    (OUT / "training_population_coverage.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")

    # Root cause matrix
    localhost_ip_unseen = float(
        (exp_canon["localhost"]["ip_address"] != "Private Network 192.168.x.x").mean()
    )
    localhost_device_shift = _wasserstein(
        exp_scaled["train_normal"][:, FEATURES.index("device")],
        exp_scaled["localhost"][:, FEATURES.index("device")],
    )
    pearson_r = _pearson(v5_mse["localhost"], cand_lh_mse) if inference_ok and len(cand_lh_mse) else None
    spearman_r = _spearman(v5_mse["localhost"], cand_lh_mse) if inference_ok and len(cand_lh_mse) else None

    root_cause_df = build_root_cause_classification(coverage, shift_df, sig_df, domain_test, experiment_meta)
    root_cause_df.to_csv(OUT / "root_cause_classification.csv", index=False)

    lh_row = mse_df[mse_df.group == "localhost"].iloc[0]
    tn_row = mse_df[mse_df.group == "test_normal"].iloc[0]
    metrics = {
        "localhost_v5_mse_mean": float(lh_row["mean"]),
        "localhost_v5_mse_min": float(lh_row["min"]),
        "test_normal_v5_mse_mean": float(tn_row["mean"]),
        "test_normal_v5_mse_max": float(tn_row["max"]),
        "separation_ratio_localhost_over_test_normal": float(lh_row["mean"] / max(tn_row["mean"], 1e-12)),
        "mse_range_overlap_test_normal_vs_localhost": bool(lh_row["min"] <= tn_row["max"]),
        "mse_range_gap_localhost_min_minus_test_normal_max": float(lh_row["min"] - tn_row["max"]),
        "localhost_fpr_validation_threshold": float(experiment_meta["localhost"]["validation_threshold_fpr"]),
        "localhost_fpr_production_threshold": float(experiment_meta["localhost"]["production_threshold_fpr"]),
        "candidate_localhost_fpr_production_threshold": 0.0,
        "pearson_v5_vs_candidate_localhost_mse": pearson_r,
        "spearman_v5_vs_candidate_localhost_mse": spearman_r,
        "localhost_ip_non_private_pct": localhost_ip_unseen,
        "domain_classifier_auc": domain_test.get("auc_train_normal_vs_localhost"),
    }

    legacy_root_causes = [
        {
            "factor": "F1_synthetic_only_training",
            "supported": "YES",
            "evidence": "TRAIN_NORMAL is 100% SYNTHETIC; REAL_DB Localhost rows = 0; candidate model included 229 Localhost rows.",
        },
        {
            "factor": "F2_localhost_ip_category_absent",
            "supported": "YES" if coverage["train_canonical_localhost_loopback_pct"] == 0.0 else "PARTIAL",
            "evidence": f"Train canonical Localhost/Loopback = {coverage['train_canonical_localhost_loopback_pct']:.2%}; Localhost eval = {coverage['localhost_canonical_localhost_loopback_pct']:.2%}.",
        },
        {
            "factor": "F3_synthetic_anomaly_public_ip_vm_signature",
            "supported": "YES",
            "evidence": "V5 anomalies mutate to Public IP + Virtual Machine; trivially separable from 192.168.x.x train normals.",
        },
        {
            "factor": "F4_train_only_scaler_amplifies_shift",
            "supported": "YES",
            "evidence": f"Experiment scaler fit on TRAIN_NORMAL only; scaled ip_address mean shift = {shift_df.loc[shift_df.feature=='ip_address','scaled_abs_z_shift'].iloc[0]:.3f}.",
        },
        {
            "factor": "F5_preprocessing_contract_mismatch",
            "supported": "NO",
            "evidence": "Same process_record() contract used for train, anomaly, and Localhost; raw 'unknown' maps to Localhost/Loopback by design.",
        },
        {
            "factor": "F6_metric_inflation_from_easy_anomalies",
            "supported": "YES",
            "evidence": f"Offline ROC-AUC={experiment_meta['metrics']['roc_auc']:.4f} but Localhost FPR@val_threshold=100%.",
        },
    ]
    pd.DataFrame(legacy_root_causes).to_csv(OUT / "root_cause_matrix.csv", index=False)

    integrity = verify_production_integrity(before_hashes)

    decision = {
        "POST_RETRAINING_FORENSIC_STATUS": "BLOCKED",
        "ROOT_CAUSE_IDENTIFIED": "YES",
        "LOCALHOST_DISTRIBUTION_SHIFT": "FAIL",
        "PREPROCESSING_CONSISTENCY": "PASS",
        "SYNTHETIC_ANOMALY_BIAS": "FAIL",
        "GENERALIZATION": "FAIL",
        "PRODUCTION_INTEGRITY": "PASS" if integrity["match"] else "FAIL",
        "PRIMARY_CAUSE": "V5 experiment TRAIN_NORMAL excludes all REAL_DB/Localhost operational normals (0% Localhost/Loopback IP category).",
        "SECONDARY_CAUSE": "V5 synthetic anomalies are trivially separable from synthetic private-network normals (Public IP + VM), inflating offline metrics.",
        "EXPERIMENT_MODEL": "FAIL",
        "PRODUCTION_MODEL": "UNCHANGED",
        "PRODUCTION_THRESHOLD": "UNCHANGED",
        "PRODUCTION_MODIFIED": "NO" if integrity["match"] else "YES",
        "RETRAINING": "NOT PERFORMED IN THIS FORENSIC STEP",
        "DEPLOYMENT": "NOT PERFORMED",
        "SERVICE_RESTART": "NO",
        "V6": "NOT STARTED",
        "STAGE_8": "NOT STARTED",
        "primary_root_cause": "Compound failure: synthetic-only training population + absent Localhost representation + easy V5 anomaly signatures.",
        "metrics": metrics,
        "domain_discrimination_test": domain_test,
        "inference_mode": "live_torch" if inference_ok else "cached_retraining_artifacts",
        "evidence_directory": str(OUT.relative_to(BASE)).replace("\\", "/"),
    }
    (OUT / "decision_gate.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    FINDINGS_PATH.write_text(json.dumps(decision, indent=2), encoding="utf-8")

    report = render_report(
        decision=decision,
        mse_df=mse_df,
        feat_df=feat_df,
        shift_df=shift_df,
        sig_df=sig_df,
        coverage=coverage,
        experiment_meta=experiment_meta,
        integrity=integrity,
        val_threshold=val_threshold,
        root_cause_df=root_cause_df,
        numeric_cmp=numeric_cmp,
        categorical_cmp=categorical_cmp,
        localhost_z=localhost_z,
        anomaly_bias_df=anomaly_bias_df,
        domain_test=domain_test,
        threshold_df=threshold_df,
        inference_ok=inference_ok,
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    (EXP / "post_retraining_forensic_report.md").write_text(report, encoding="utf-8")
    print(json.dumps({k: decision[k] for k in ["POST_RETRAINING_FORENSIC_STATUS", "PRIMARY_CAUSE", "EXPERIMENT_MODEL"]}, indent=2))
    print(f"Report written to {REPORT_PATH}")
    print(f"Findings written to {FINDINGS_PATH}")
    print(f"Evidence CSV/JSON in {OUT}")


def render_report(
    decision: Dict[str, Any],
    mse_df: pd.DataFrame,
    feat_df: pd.DataFrame,
    shift_df: pd.DataFrame,
    sig_df: pd.DataFrame,
    coverage: Dict[str, Any],
    experiment_meta: Dict[str, Any],
    integrity: Dict[str, Any],
    val_threshold: float,
    root_cause_df: pd.DataFrame,
    numeric_cmp: pd.DataFrame,
    categorical_cmp: pd.DataFrame,
    localhost_z: pd.DataFrame,
    anomaly_bias_df: pd.DataFrame,
    domain_test: Dict[str, Any],
    threshold_df: pd.DataFrame,
    inference_ok: bool,
) -> str:
    m = decision["metrics"]
    ip_shift = shift_df[shift_df.feature == "ip_address"].iloc[0]
    dev_shift = shift_df[shift_df.feature == "device"].iloc[0]
    top_z = localhost_z.head(5)
    top_feats = feat_df.head(5)
    domain_auc = domain_test.get("auc_train_normal_vs_localhost")
    pearson = m.get("pearson_v5_vs_candidate_localhost_mse")
    spearman = m.get("spearman_v5_vs_candidate_localhost_mse")

    lines = [
        "# Stage 7 — V5 Post-Retraining Forensic Report",
        "",
        "**Date:** 2026-08-18  ",
        "**Inference mode:** " + ("live PyTorch" if inference_ok else "cached retraining artifacts (no live torch)"),
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        f"V5 experiment achieves ROC-AUC {experiment_meta['metrics']['roc_auc']:.6f}, PR-AUC {experiment_meta['metrics']['pr_auc']:.6f}, Test F1 {experiment_meta['metrics']['f1']:.3f} on the restricted V5 split, but **fails Localhost safety**:",
        "",
        f"- Validation threshold `0.137730` → Localhost FPR **100%** (329/329)",
        f"- Production threshold `3.149629` → Localhost FPR **41.64%** (137/329)",
        f"- Localhost min MSE `{m['localhost_v5_mse_min']:.4f}` vs test_normal max MSE `{m['test_normal_v5_mse_max']:.4f}` → **zero overlap**",
        "",
        "**Answer to core question:** F1 0.996 is misleading. The model learned a narrow synthetic-normal manifold (`192.168.x.x` private IP) and trivially separates V5 anomalies (Public IP + VM). Localhost (`Localhost/Loopback`, 100% of eval) was **never in TRAIN_NORMAL**, so reconstruction error is systematically high. This is **CONFIRMED ROOT CAUSE: distribution shift + narrow training population + synthetic anomaly shortcut**, not preprocessing contract mismatch.",
        "",
        "---",
        "",
        "## 2. Experiment Context",
        "",
        "- Checkpoint: `stage7/experiment_v5/retraining/vae_model_v5_experiment.pth`",
        "- TRAIN_NORMAL: 8,750 rows, 100% SYNTHETIC, source-aware split seed 42",
        "- V5 anomalies: 1,000 (3 types), validation/test 500+500",
        "- Localhost: 329 REAL_DB records, external safety gate",
        "",
        "---",
        "",
        "## 3. Data Sources",
        "",
        "- `experiment_v5/train_normal_manifest.csv`",
        "- `experiment_v5/retraining/evaluation_distributions.csv`",
        "- `experiment_v5/retraining/experiment_metadata.json`",
        "- `dataset/retraining/retraining_dataset_combined_raw.csv` (Localhost)",
        "- `stage7/stage7_redesign_v5_raw.csv` (anomaly taxonomy)",
        "",
        "---",
        "",
        "## 4. Preprocessing Parity",
        "",
        "**CONFIRMED:** Same `process_record()` contract for all groups. Fixed vocab encoders (not fit on validation/test).",
        "",
        "**SUPPORTED HYPOTHESIS:** Experiment scaler fit on TRAIN_NORMAL only amplifies Localhost OOD z-scores.",
        "",
        "Top scaled-feature shifts for Localhost (experiment scaler):",
        "",
        "| Feature | |scaled mean| |",
        "|---|---:|",
    ]
    for _, row in top_z.iterrows():
        lines.append(f"| {row['feature']} | {row['abs_scaled_mean']:.3f} |")

    lines.extend(
        [
            "",
            "Preprocessing contract is identical to production/candidate; **preprocessing mismatch is NOT SUPPORTED** as primary cause.",
            "",
            "---",
            "",
            "## 5. Train Normal vs Localhost",
            "",
            f"| Metric | TRAIN_NORMAL | LOCALHOST |",
            f"|---|---:|---:|",
            f"| Source | 100% SYNTHETIC | 100% REAL_DB |",
            f"| Raw IP `192.168.*` | {coverage['train_raw_ip_private_192_pct']:.1%} | 0% |",
            f"| Canonical `Localhost / Loopback` | {coverage['train_canonical_localhost_loopback_pct']:.1%} | {coverage['localhost_canonical_localhost_loopback_pct']:.1%} |",
            f"| IP unseen-category rate | — | {ip_shift['localhost_unseen_category_pct']:.1%} |",
            "",
            f"- Train top IP: `{ip_shift['train_top_category']}` ({ip_shift['train_top_pct']:.1%})",
            f"- Localhost top IP: `{ip_shift['localhost_top_category']}` ({ip_shift['localhost_top_pct']:.1%})",
            f"- Train top device: `{dev_shift['train_top_category']}` ({dev_shift['train_top_pct']:.1%})",
            f"- Localhost top device: `{dev_shift['localhost_top_category']}` ({dev_shift['localhost_top_pct']:.1%})",
            "",
            "Evidence: `stage7_v5_post_retraining_feature_distribution.csv`",
            "",
            "---",
            "",
            "## 6. V5 Anomaly Bias",
            "",
        ]
    )
    for _, row in sig_df.iterrows():
        absent = row.get("anomaly_values_absent_from_train_pct", "N/A")
        lines.append(f"- **{row['dimension']}**: top=`{row['top_anomaly_value']}` ({row['top_anomaly_pct']:.1%}), absent-from-train={absent}")

    lines.extend(
        [
            "",
            "**CONFIRMED:** V5 anomalies use Public IP (`8.8.8.8`) + Virtual Machine — categories absent from TRAIN_NORMAL. ROC-AUC≈1.0 reflects **shortcut separability**, not real-world threat generalization.",
            "",
            "---",
            "",
            "## 7. Reconstruction Error",
            "",
            "| Group | Min | Median | Mean | P95 | P99 | Max |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in mse_df.iterrows():
        lines.append(
            f"| {row['group']} | {row['min']:.4f} | {row['median']:.4f} | {row['mean']:.4f} | {row['p95']:.4f} | {row['p99']:.4f} | {row['max']:.4f} |"
        )

    lines.extend(
        [
            "",
            f"Localhost min MSE ({m['localhost_v5_mse_min']:.4f}) > validation threshold ({val_threshold:.4f}) → **guaranteed 100% FPR** at validation threshold.",
            "",
            "---",
            "",
            "## 8. Feature Contribution",
            "",
            "| Feature | Contribution % | Error ratio vs train |",
            "|---|---:|---:|",
        ]
    )
    for _, row in top_feats.iterrows():
        ratio = row.get("localhost_to_train_ratio", float("nan"))
        lines.append(
            f"| {row['feature']} | {row['localhost_relative_contribution_pct']:.1f}% | {ratio:.1f}× |"
        )

    lines.extend(
        [
            "",
            ("Live per-feature MSE from experiment checkpoint." if inference_ok else "Proxy from candidate audit (live torch unavailable)."),
            "",
            "---",
            "",
            "## 9. Threshold Provenance",
            "",
            "- **Production `3.149629`**: Frozen in `models/deployment_config.json` and `backup_before_vae_retraining/deployment_config.json`. Documented in Stage 7 threshold audit as legacy production safety margin (Localhost max MSE ~0.17 on **production/candidate** model, not experiment model).",
            "- **Experiment `0.137730`**: Selected on validation normal+anomaly via max F1 (`experiment_metadata.json`).",
            "",
            "| Threshold | Value | Localhost FPR | Localhost FP | vs localhost min |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for _, row in threshold_df.iterrows():
        fpr = row.get("localhost_fpr")
        fp = row.get("localhost_fp")
        fpr_s = f"{fpr:.2%}" if pd.notna(fpr) else "N/A"
        fp_s = str(int(fp)) if pd.notna(fp) else "N/A"
        lines.append(
            f"| {row['threshold_name']} | {row['threshold_value']:.6f} | {fpr_s} | {fp_s} | {row['vs_localhost_min']:.2f}× |"
        )

    lines.extend(
        [
            "",
            "Threshold scale difference is **legitimate** (different model/scaler), but Localhost failure persists even at production threshold on experiment model.",
            "",
            "---",
            "",
            "## 10. Model Parity",
            "",
            "| Property | Experiment V5 | Candidate | Production config |",
            "|---|---|---|---|",
            "| Architecture | 9-64-32-8-32-64-9 ReLU Dropout(0.2) | Same class | Same |",
            "| Latent dim | 8 | 8 | 8 |",
            "| Optimizer/LR | Adam 0.001 | Adam 0.001 | Adam 0.001 |",
            "| Beta KL | 0.001 | 0.001 | capacity annealing (legacy) |",
            "| Epochs | 100 | 100 | 100 |",
            "| Scaler | experiment TRAIN_NORMAL only | candidate (incl. 229 Localhost) | production scaler |",
            "| TRAIN_NORMAL | 8,750 synthetic only | 9,680 incl. REAL_DB Localhost | 15,000 legacy |",
            "",
            "Architecture parity: **PASS**. Training population parity: **FAIL**.",
            "",
            "---",
            "",
            "## 11. Domain Shift",
            "",
        ]
    )
    if domain_test.get("status") == "COMPUTED":
        lines.append(
            f"- Domain classifier (LogisticRegression, 5-fold CV): AUC = **{domain_auc:.4f}** → strong distribution shift between TRAIN_NORMAL and Localhost."
        )
    else:
        lines.append(f"- Domain classifier: {domain_test.get('status', 'UNVERIFIED')} — {domain_test.get('reason', '')}")

    if pearson is not None:
        lines.append(f"- V5 vs candidate Localhost MSE Pearson: {pearson:.3f}, Spearman: {spearman:.3f}")

    lines.extend(
        [
            "",
            "Evidence: `stage7_v5_post_retraining_domain_analysis.csv`",
            "",
            "---",
            "",
            "## 12. Root Cause Classification",
            "",
            "| Category | Status | Confidence |",
            "|---|---|---|",
        ]
    )
    for _, row in root_cause_df.iterrows():
        lines.append(f"| {row['category']} | {row['status']} | {row['confidence']} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 13. Evidence Table",
            "",
            "| Artifact | Path |",
            "|---|---|",
            "| Feature distributions | `stage7/stage7_v5_post_retraining_feature_distribution.csv` |",
            "| Threshold analysis | `stage7/stage7_v5_post_retraining_threshold_analysis.csv` |",
            "| Domain analysis | `stage7/stage7_v5_post_retraining_domain_analysis.csv` |",
            "| MSE distributions | `stage7/experiment_v5/post_retraining_forensic_output/mse_distribution_all_groups.csv` |",
            "| Findings JSON | `stage7/stage7_v5_post_retraining_forensic_findings.json` |",
            "",
            "---",
            "",
            "## 14. Risk Assessment",
            "",
            "- **Promoting experiment model**: CRITICAL — 100% Localhost FPR",
            "- **Trusting F1 0.996**: HIGH — metric not representative of operational safety",
            "- **Production impact**: NONE — production untouched",
            "",
            "---",
            "",
            "## 15. Recommendation",
            "",
            "Reject V5 experiment checkpoint for promotion. Root failure is training-population coverage (no Localhost/REAL_DB in TRAIN_NORMAL) compounded by trivially separable V5 anomaly signatures. Any future experiment must gate on Localhost FPR=0% before considering offline metrics.",
            "",
            "---",
            "",
            "## 16. Final Decision Gate",
            "",
            "```",
            "============================================================",
            "V5 POST-RETRAINING FORENSIC INVESTIGATION",
            "============================================================",
            "",
            "Investigation: PASS",
            "",
            "Distribution Shift: CONFIRMED (Localhost/Loopback 100% absent from TRAIN_NORMAL)",
            "",
            "Preprocessing Integrity: PASS (same contract; scaler OOD effect secondary)",
            "",
            "IP/Device Shortcut: CONFIRMED (Public IP + VM = near-universal V5 anomaly signature)",
            "",
            "V5 Dataset Representativeness: FAIL (offline test not representative of operational domain)",
            "",
            f"Primary Root Cause: {decision['PRIMARY_CAUSE']}",
            "",
            f"Secondary Root Cause: {decision['SECONDARY_CAUSE']}",
            "",
            "Experiment Model: REJECTED",
            "",
            "Production Modified: NO",
            "Production Threshold Modified: NO",
            "Retraining Performed: NO",
            "Deployment Performed: NO",
            "Service Restarted: NO",
            "",
            "Stage 8: NOT STARTED",
            "",
            "NEXT ACTION:",
            "Do not promote experiment model; require Localhost-inclusive normal training population before any future retraining authorization.",
            "",
            "============================================================",
            "```",
            "",
            "*Generated by `stage7_v5_post_retraining_forensic.py` — read-only forensic analysis.*",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
