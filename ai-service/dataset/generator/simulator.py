from flows import WORKFLOWS
from utils import next_timestamp, random_session_id, random_timestamp


class SessionBuilder:
    def build(self, role):
        session_id = random_session_id()
        current_time = random_timestamp()
        session = []
        for activity in WORKFLOWS[role]:
            session.append({"session_id": session_id, "timestamp": current_time, "activity": activity})
            current_time = next_timestamp(current_time)
        return session
