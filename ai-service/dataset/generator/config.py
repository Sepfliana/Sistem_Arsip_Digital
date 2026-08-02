from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "raw"
OUTPUT_FILE = RAW_DIR / "audit_log_dataset.csv"
OUTPUT_PATH = OUTPUT_FILE

TOTAL_ROWS = 15000
TOTAL_EVENTS = TOTAL_ROWS
RANDOM_SEED = 42

WORK_START = 7
WORK_END = 17

DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "sistem_arsip_digital"
DB_USER = "postgres"
DB_PASSWORD = "qethipen29"

INTERNAL_IP_PREFIX = "192.168.1."
EXTERNAL_IP_PREFIXES = [
    "8.", "20.", "36.", "45.", "66.",
    "103.", "114.", "139.", "157.", "180.",
]

NORMAL_RATIO = 0.90
ANOMALY_RATIO = 0.10
ANOMALY_RATE = ANOMALY_RATIO
ANOMALY_DISTRIBUTION = {
    "login_luar_jam": 0.30,
    "ip_berubah": 0.20,
    "device_berubah": 0.15,
    "aktivitas_terlalu_cepat": 0.12,
    "durasi_tidak_wajar": 0.10,
    "peminjaman_massal": 0.08,
    "verifikasi_massal": 0.05,
}
