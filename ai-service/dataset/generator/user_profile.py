from config import WORK_END, WORK_START
from utils import random_device, random_internal_ip


class UserProfile:
    def __init__(self, user):
        self.user_id = user["user_id"]
        self.username = user["username"]
        self.role = user["role"]
        self.device = random_device()
        self.internal_ip = random_internal_ip()
        self.work_start = WORK_START
        self.work_end = WORK_END

    def to_dict(self):
        return {"user_id": self.user_id, "username": self.username, "role": self.role, "device": self.device, "internal_ip": self.internal_ip, "work_start": self.work_start, "work_end": self.work_end}
