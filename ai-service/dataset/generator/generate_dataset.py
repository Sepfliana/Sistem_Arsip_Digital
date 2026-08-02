import csv
import random

from activity_profile import ACTIVITY_PROFILE
from anomaly import AnomalyEngine
from config import ANOMALY_DISTRIBUTION, ANOMALY_RATIO, OUTPUT_FILE, RANDOM_SEED, TOTAL_ROWS
from db_loader import DatabaseLoader
from flows import WORKFLOWS
from simulator import SessionBuilder
from user_profile import UserProfile
from utils import random_duration, random_object_count


FIELDS = ["timestamp", "session_id", "user_id", "username", "role", "activity", "status", "ip_address", "device", "duration_ms", "object_count", "risk_level", "anomaly_type"]


class DatasetGenerator:
    def __init__(self):
        self.session_builder = SessionBuilder()
        self.anomaly_engine = AnomalyEngine()

    def _load_profiles(self):
        loader = DatabaseLoader()
        try:
            loader.connect()
            users = loader.load_active_users()
        finally:
            loader.close()
        if not users:
            raise ValueError("Tidak ada user aktif dengan role Admin, Arsiparis, atau User.")
        return [UserProfile(user).to_dict() for user in users]

    @staticmethod
    def _can_complete(remaining):
        return remaining == 0 or (remaining >= 4 and remaining != 7)

    def _generate_rows(self, profiles):
        rows = []
        remaining = TOTAL_ROWS
        while remaining:
            candidates = [profile for profile in profiles if len(WORKFLOWS[profile["role"]]) <= remaining and self._can_complete(remaining - len(WORKFLOWS[profile["role"]]))]
            profile = random.choice(candidates)
            for event in self.session_builder.build(profile["role"]):
                characteristics = ACTIVITY_PROFILE[event["activity"]]
                rows.append({
                    "timestamp": event["timestamp"], "session_id": event["session_id"],
                    "user_id": profile["user_id"], "username": profile["username"], "role": profile["role"],
                    "activity": event["activity"], "status": "Berhasil", "ip_address": profile["internal_ip"],
                    "device": profile["device"], "duration_ms": random_duration(characteristics["duration"]),
                    "object_count": random_object_count(characteristics["object_count"]),
                    "risk_level": "Normal", "anomaly_type": "Normal",
                })
            remaining = TOTAL_ROWS - len(rows)
        eligible_indices = [
            index for index, row in enumerate(rows)
            if row["activity"] in {"Login", "Verifikasi", "Input Berkas", "Peminjaman"}
        ]
        for index in random.sample(eligible_indices, int(TOTAL_ROWS * 0.03)):
            rows[index]["status"] = "Gagal"
        return rows

    def _inject_anomalies(self, rows):
        anomaly_total = int(TOTAL_ROWS * ANOMALY_RATIO)
        counts = {name: int(anomaly_total * ratio) for name, ratio in ANOMALY_DISTRIBUTION.items()}
        login_indices = [index for index, row in enumerate(rows) if row["activity"] == "Login"]
        selected = set(random.sample(login_indices, counts["login_luar_jam"]))
        assignments = {index: "login_luar_jam" for index in selected}
        available = set(range(len(rows))) - selected
        for name, count in counts.items():
            if name == "login_luar_jam":
                continue
            indices = random.sample(sorted(available), count)
            for index in indices:
                assignments[index] = name
            selected.update(indices)
            available.difference_update(indices)
        for index, anomaly in assignments.items():
            self.anomaly_engine.apply(rows[index], anomaly)

    def run(self):
        random.seed(RANDOM_SEED)
        rows = self._generate_rows(self._load_profiles())
        self._inject_anomalies(rows)
        rows.sort(key=lambda row: row["timestamp"])
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            for row in rows:
                row["timestamp"] = row["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow(row)
        return OUTPUT_FILE


def main():
    DatasetGenerator().run()


if __name__ == "__main__":
    main()
