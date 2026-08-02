import random
from datetime import datetime, timedelta

from config import EXTERNAL_IP_PREFIXES, INTERNAL_IP_PREFIX, WORK_END, WORK_START


def random_timestamp():
    start = datetime(2025, 1, 1)
    day = start + timedelta(days=random.randint(0, 364))
    return day + timedelta(seconds=random.randint(WORK_START * 3600, WORK_END * 3600))


def random_internal_ip():
    return f"{INTERNAL_IP_PREFIX}{random.randint(2, 254)}"


def random_external_ip():
    return "{}{}.{}.{}".format(random.choice(EXTERNAL_IP_PREFIXES), random.randint(0, 255), random.randint(0, 255), random.randint(1, 254))


def random_session_id():
    return f"S{random.getrandbits(64):016X}"


def next_timestamp(current_time):
    return current_time + timedelta(seconds=random.randint(10, 180))


def random_duration(duration_range=(300, 12000)):
    return random.randint(*duration_range)


def random_object_count(object_range=(1, 10)):
    return random.randint(*object_range)


def random_device():
    return random.choice(["Windows", "Laptop Windows", "PC Windows", "Android", "iPhone"])


def random_anomaly_device():
    return random.choice(["Linux", "MacOS", "Unknown Device", "Virtual Machine"])
