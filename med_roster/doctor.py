class Doctor:
    def __init__(self, name, role, FTE, availability):
        self.name = name
        self.role = role
        self.FTE = FTE
        self.availability = availability  # List of available shifts (e.g., [0, 1, 2])


class Shift:
    def __init__(self, shift_type, duration, role_requirements, min_doctors, start_time, end_time):
        self.shift_type = shift_type
        self.duration = duration
        self.role_requirements = role_requirements
        self.min_doctors = min_doctors
        self.start_time = start_time
        self.end_time = end_time
        self.start_minutes = self._to_minutes(start_time)
        self.end_minutes = self._to_minutes(end_time)
        self.spans_midnight = self.end_minutes <= self.start_minutes
        self.clock_duration_minutes = (
            self.end_minutes - self.start_minutes
            if not self.spans_midnight
            else (1440 - self.start_minutes) + self.end_minutes
        )

    @staticmethod
    def _to_minutes(time_str):
        hours, minutes = time_str.split(':')
        return int(hours) * 60 + int(minutes)

        # start_time/end_time are 24-hour "HH:MM" clock strings, e.g. "08:00".
        # A shift is treated as spanning midnight whenever end_time is not
        # strictly after start_time (covers both genuinely overnight shifts
        # like "20:00"-"08:00", and shifts that end exactly at midnight,
        # "16:00"-"00:00", which land at the same instant as the following
        # day's 00:00).