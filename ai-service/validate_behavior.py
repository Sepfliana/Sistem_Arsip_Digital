import json
from pathlib import Path
import pandas as pd

from schemas.predict_request import PredictRequest
from app import predict_audit_log, initialise_inference

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "dataset" / "generator" / "raw" / "audit_log_dataset.csv"


def row_to_payload(row: pd.Series) -> dict:
    return {
        "waktu": str(row["timestamp"]),
        "user_id": int(row["user_id"]),
        "aksi": str(row["activity"]),
        "status": str(row["status"]),
        "device": str(row["device"]),
        "ip_address": str(row["ip_address"]),
        "durasi_ms": float(row["duration_ms"]),
        "jumlah_objek": float(row["object_count"]),
    }


def main():
    initialise_inference()
    df = pd.read_csv(DATASET_PATH, encoding="utf-8-sig")

    # 1. Normal Sample
    normal_df = df[(df["risk_level"] == "Normal") & (df["anomaly_type"] == "Normal")]
    normal_row = normal_df.iloc[0]
    normal_payload = row_to_payload(normal_row)
    normal_res = predict_audit_log(PredictRequest(**normal_payload)).model_dump()

    # 2. Anomaly Sample
    anomaly_df = df[(df["risk_level"] != "Normal") | (df["anomaly_type"] != "Normal")]
    anomaly_row = anomaly_df.iloc[0]
    anomaly_payload = row_to_payload(anomaly_row)
    anomaly_res = predict_audit_log(PredictRequest(**anomaly_payload)).model_dump()

    print("=== VALIDASI PERILAKU MODEL VAE ===")

    print("\n--- 1. PENGUJIEN DATA NORMAL ---")
    print("Payload:")
    print(json.dumps(normal_payload, indent=2))
    print("Hasil Inference:")
    print(f"  anomaly_score : {normal_res['anomaly_score']}")
    print(f"  threshold     : {normal_res['threshold']}")
    print(f"  is_anomaly    : {normal_res['is_anomaly']}")
    print(f"  risk_level    : {normal_res['risk_level']}")
    print(f"  status        : {normal_res['status']}")

    print("\n--- 2. PENGUJIEN DATA ANOMALI ---")
    print("Payload:")
    print(json.dumps(anomaly_payload, indent=2))
    print("Metadata CSV (anomaly_type):", anomaly_row.get("anomaly_type"))
    print("Hasil Inference:")
    print(f"  anomaly_score : {anomaly_res['anomaly_score']}")
    print(f"  threshold     : {anomaly_res['threshold']}")
    print(f"  is_anomaly    : {anomaly_res['is_anomaly']}")
    print(f"  risk_level    : {anomaly_res['risk_level']}")
    print(f"  status        : {anomaly_res['status']}")

    print("\n--- KESIMPULAN ---")
    if not normal_res['is_anomaly'] and anomaly_res['is_anomaly']:
        print("Model VAE BERHASIL membedakan data normal dan data anomali secara konsisten.")
    else:
        print(f"Hasil Perbandingan: Normal is_anomaly={normal_res['is_anomaly']}, Anomaly is_anomaly={anomaly_res['is_anomaly']}")


if __name__ == "__main__":
    main()
