from fastapi.testclient import TestClient
from app import app


def test_fastapi_endpoints():
    client = TestClient(app)

    # 1. Health check
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"server": "OK", "model": "READY"}
    print("Health Check Response:", response.json())

    # 2. Predict endpoint with backend NodeJS payload
    payload = {
        "waktu": "2026-07-13T10:00:00.000Z",
        "user_id": 1,
        "aksi": "CREATE_BERKAS",
        "target_tipe": "BERKAS",
        "ip_address": "unknown",
        "device": "unknown",
        "status": "SUCCESS",
        "durasi_ms": 0,
        "jumlah_objek": 1,
        "integrity_status": "UNKNOWN",
        "hasil_hash": "UNKNOWN",
    }

    response = client.post("/predict", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    print("Predict Response:", data)

    # Verify contract
    assert "anomaly_score" in data
    assert "reconstruction_error" in data
    assert "threshold" in data
    assert "risk_level" in data
    assert "timestamp" in data
    assert "is_anomaly" in data
    assert "status" in data
    assert "score" in data
    assert data["status"] in {"NORMAL", "ANOMALY"}
    assert data["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
    print("All contract assertions passed successfully!")


if __name__ == "__main__":
    test_fastapi_endpoints()
