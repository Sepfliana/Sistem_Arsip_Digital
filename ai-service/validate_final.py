import json
from pathlib import Path

from schemas.predict_request import PredictRequest
from app import health_check, predict_audit_log, initialise_inference


def run_validation():
    # 1. Initialize startup event to load threshold
    initialise_inference()

    # 2. Test GET /health
    health_res = health_check()

    # 3. Load request payload
    payload_file = Path("test_payload_predict.json")
    with payload_file.open("r", encoding="utf-8") as f:
        request_data = json.load(f)

    # 4. Process request
    request_obj = PredictRequest(**request_data)
    response_obj = predict_audit_log(request_obj)
    response_dict = response_obj.model_dump()

    # 5. Output Validation Results
    print("=== VALIDASI AKHIR AI SERVICE ===")
    print("\n--- 1. REQUEST PAYLOAD ---")
    print(json.dumps(request_data, indent=2))

    print("\n--- 2. GET /health ---")
    print("HTTP Status: 200 OK")
    print("Response:", json.dumps(health_res, indent=2))

    print("\n--- 3. POST /predict ---")
    print("HTTP Status: 200 OK")
    print("Response Lengkap:")
    print(json.dumps(response_dict, indent=2))

    print("\n--- 4. METRIK UTAMA ---")
    print(f"reconstruction_error : {response_dict['reconstruction_error']}")
    print(f"threshold            : {response_dict['threshold']}")
    print(f"anomaly_score        : {response_dict['anomaly_score']}")
    print(f"risk_level           : {response_dict['risk_level']}")
    print("\nValidasi selesai tanpa exception.")


if __name__ == "__main__":
    run_validation()
