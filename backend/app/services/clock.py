from datetime import datetime, timedelta

class ClockService:
    def __init__(self):
        self._current_time = datetime.utcnow()
        self._is_simulated = False

    def get_time(self) -> datetime:
        return self._current_time

    def set_time(self, new_time: datetime):
        self._current_time = new_time
        self._is_simulated = True

    def advance(self, hours: int):
        self._current_time += timedelta(hours=hours)

# Global clock instance for the application
clock = ClockService()
