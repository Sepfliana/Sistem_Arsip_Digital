import random

from config import ANOMALY_DISTRIBUTION, ANOMALY_RATE, WORK_END, WORK_START
from utils import random_anomaly_device, random_external_ip


class AnomalyEngine:
    def __init__(self):
        self.anomalies = list(ANOMALY_DISTRIBUTION)
        self.weights = list(ANOMALY_DISTRIBUTION.values())

    def apply(self, event, anomaly=None):
        if anomaly is None:
            if random.random() >= ANOMALY_RATE:
                return event
            anomaly = random.choices(self.anomalies, weights=self.weights, k=1)[0]

        event["anomaly_type"] = anomaly
        if anomaly == "login_luar_jam":
            event["timestamp"] = event["timestamp"].replace(hour=random.randint(0, WORK_START - 1))
            event["risk_level"] = "Low"
        elif anomaly == "ip_berubah":
            event["ip_address"] = random_external_ip()
            event["risk_level"] = "Low"
        elif anomaly == "device_berubah":
            event["device"] = random_anomaly_device()
            event["risk_level"] = "Low"
        elif anomaly == "durasi_tidak_wajar":
            event["duration_ms"] *= random.randint(5, 10)
            event["risk_level"] = "Medium"
        elif anomaly == "aktivitas_terlalu_cepat":
            event["duration_ms"] = random.randint(1, 100)
            event["risk_level"] = "Medium"
        elif anomaly == "peminjaman_massal":
            event["object_count"] = random.randint(30, 100)
            event["risk_level"] = "High"
        elif anomaly == "verifikasi_massal":
            event["object_count"] = random.randint(50, 200)
            event["risk_level"] = "High"
        return event
