from ortools.sat.python import cp_model
from app import model, all_nurses, all_shifts, all_days, shifts

#Variables:
MORNING_SHIFT = [0,1] #8hr and 12hr day shifts
MID_MORNING_SHIFT = [2] #10am - 6pm
EVENING_SHIFT = [3] #4pm to midnight
NIGHT_SHIFT = [4,5] #8hr and 12hr night shift


SHIFT_DURATION = {
    'MORNING_SHIFT': 8,
    'MID_MORNING_SHIFT': 8,
    'EVENING_SHIFT': 8,
    'NIGHT_SHIFT': 8,
    'WEEKEND_DAY_SHIFT': 12,
    'WEEKEND_NIGHT_SHIFT': 12,
    'ADO_SHIFT': 8
}

#Constraints:
def assign_doctors_to_shifts(model, shifts, all_doctors, all_days, all_shifts):
# - Each shift is assigned to a single doctor per day
    for d in all_days:
        for s in all_shifts:
            model.add_exactly_one(shifts[(n, d, s)] for n in all_doctors)    

# - Each doctor works at most one shift per day
    for n in all_doctors:
        for d in all_days:
            model.add_at_most_one(shifts[(n, d, s)] for s in all_shifts)

# - There are no consecutive shifts for a doctor
    for n in all_doctors:
        for d in all_days:
            for s in all_shifts:
                if s < len(all_shifts) - 1:
                    model.add(shifts[(n, d, s)] + shifts[(n, d, s + 1)] <= 1)

# -There is a minimum rest period of 10 hours between shifts for a doctor
    for n in all_doctors:
        for d in all_days:
            if d < len(all_days) - 1:
                model.add(shifts[(n, d + 1, s_morn)] for s_morn in MORNING_SHIFT) 

# - Full time doctors work 80 hours per 14 day period (38 hours per week + accumulates 1 ADO every 28 days)
    for n in all_doctors:
        total_hours_worked = sum(
            shifts[(n, d, s)] * SHIFT_DURATION.get(s, 0) for d in all_days for s in all_shifts)
        model.add(total_hours_worked == 80)

# - Full time equivalent  = 1.0 FTE x 38 hours per week so 0.5 FTE = 19 hours per week
    if FTE == 1.0:
        hours = 152
    else:
        hours = 152 * FTE

# - Any hours worked > 10 hours in a day is considered overtime
    for n in all_doctors:
        for d in all_days:
            total_hours_worked = sum(
                shifts[(n, d, s)] * SHIFT_DURATION.get(s, 0) for s in all_shifts)
            model.add(total_hours_worked <= 10)