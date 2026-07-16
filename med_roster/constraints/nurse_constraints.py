from ortools.sat.python import cp_model
from med_roster.google_nurse import model, all_nurses, all_shifts, all_days, shifts

#Variables:
MORNING_SHIFT = [0,1] #8hr and 12hr day shifts
AFTERNOON_SHIFT = [2] #11:30am - 8:00pm
NIGHT_SHIFT = 3 #12hr night shift

#Constraints:

# - Each shift is assigned to a single nurse per day
def assign_nurses_to_shifts(model, shifts, all_nurses, all_days, all_shifts):
    for d in all_days:
        for s in all_shifts:
            model.add_exactly_one(shifts[(n, d, s)] for n in all_nurses)    

# - Each nurse works at most one shift per day
    for n in all_nurses:
        for d in all_days:
            model.add_at_most_one(shifts[(n, d, s)] for s in all_shifts)

# - There are no consecutive shifts for a nurse
    for n in all_nurses:
        for d in all_days:
            for s in all_shifts:
                if s < len(all_shifts) - 1:
                    model.add(shifts[(n, d, s)] + shifts[(n, d, s + 1)] <= 1)

# -There is a minimum rest period of 11.5 hours between shifts for a nurse
    for n in all_nurses:
        for d in all_days:
            if d < len(all_days) - 1:
                model.add(shifts[(n, d + 1, s_morn)] for s_morn in MORNING_SHIFT) 

# - Full time nurses work 152 hours per 4 week period (38 hours per week)
    for n in all_nurses:
        total_hours_worked = sum(
            shifts[(n, d, s)] * 12 for d in all_days for s in all_shifts)
        model.add(total_hours_worked == 152)

# - Full time equivalent  = 1.0 FTE x 38 hours per week so 0.5 FTE = 19 hours per week
    if FTE == 1.0:
        hours = 152
    else:
        hours = 152 * FTE


# Full time nurses work 12 x 12 hour shifts and 1 x 8 hour shift per 4 week period
    for n in all_nurses:
        total_shifts_worked = sum(
            shifts[(n, d, s)] for d in all_days for s in all_shifts)
        model.add(total_shifts_worked == 13)

        