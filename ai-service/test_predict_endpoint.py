from predict import predict_audit_log


def test_predict_endpoint_accepts_backend_payload():
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

    body = predict_audit_log(payload)

    print("Prediction Output:", body)
    assert "anomaly_score" in body
    assert "reconstruction_error" in body
    assert "score" in body
    assert "threshold" in body
    assert "risk_level" in body
    assert "timestamp" in body
    assert "is_anomaly" in body
    assert body["status"] in {"NORMAL", "ANOMALY"}
    assert body["risk_level"] in {"LOW", "MEDIUM", "HIGH"}


if __name__ == "__main__":
    test_predict_endpoint_accepts_backend_payload()
