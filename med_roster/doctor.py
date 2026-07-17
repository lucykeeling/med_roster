class Doctor:
    def __init__(self, name, role, FTE, availability):
        self.name = name
        self.role = role
        self.FTE = FTE
        self.availability = availability  # List of available shifts (e.g., [0, 1, 2])


class Shift:
    def __init__(self, shift_type, duration, role_requirements, min_doctors):
        self.shift_type = shift_type
        self.duration = duration
        self.role_requirements = role_requirements
        self.min_doctors = min_doctors
