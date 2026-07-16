from ortools.sat.python import cp_model
from med_roster.google_nurse import model, all_nurses, all_shifts, all_days, shifts

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


# - Minimum of 4 days off per fortnight for full time doctors
    for n in all_doctors:
        for fortnight in range(0, len(all_days), 14):
            days_off = sum(1 - shifts[(n, d, s)] for d in range(fortnight, min(fortnight + 14, len(all_days))) for s in all_shifts)
            model.add(days_off >= 4)

# - Days off should be consecutive where possible (SOFT CONSTRAINT)
# Create a dictionary to hold "is day off" variables
    day_off = {}
    for n in all_doctors:
        for d in all_days:
            day_off[(n, d)] = model.new_bool_var(f"day_off_doc{n}_day{d}")
        
        # day_off is 1 ONLY if the sum of all shifts that day is 0
        model.add(sum(shifts[(n, d, s)] for s in all_shifts) == 0).only_enforce_if(day_off[(n, d)])
        model.add(sum(shifts[(n, d, s)] for s in all_shifts) > 0).only_enforce_if(day_off[(n, d)].not())

    consecutive_days_off = []

    for n in all_doctors:
        for d in range(len(all_days) - 1):
            is_consecutive = model.new_bool_var(f"consec_off_doc{n}_day{d}")
        
        # is_consecutive is true IF AND ONLY IF day d is off AND day d+1 is off
        model.add_bool_and([day_off[(n, d)], day_off[(n, d+1)]]).only_enforce_if(is_consecutive)
        model.add_bool_or([day_off[(n, d)].not(), day_off[(n, d+1)].not()]).only_enforce_if(is_consecutive.not())
        
        consecutive_days_off.append(is_consecutive)

# Somewhere near the end of your model setup where you define the objective:
        reward_weight = 10 # Adjust this weight based on how important this rule is to you

# If you are maximizing:
        model.maximize(sum(consecutive_days_off) * reward_weight + other_objectives)

# Or if your model minimizes penalties/costs, you would subtract it or penalize isolated days off instead.



#====================Shift Constraints: ==============================

# - Each shift has a minimum number of doctors assigned to it
WEEKDAY_MORNING_SHIFT = 8
WEEKDAY_AFTERNOON_SHIFT = 6
WEEKDAY_NIGHT_SHIFT = 4
WEEKEND_DAY_SHIFT_12 = 4
WEEKEND_DAY_SHIFT_8 = 6
WEEKEND_NIGHT_SHIFT = 6


# - Skill mix


# - Maximise fairness in weekend shift allocation (SOFT CONSTRAINT)
    for n in all_doctors:
        weekend_shifts_worked = sum(shifts[(n, d, s)] for d in all_days for s in WEEKEND_SHIFTS)
        model.add(weekend_shifts_worked <= max_weekend_shifts_per_doctor)

        reward_weight = 10 # Adjust this weight based on how important this rule is to you

# - Maximise fairness in night shift allocation (SOFT CONSTRAINT)
    for n in all_doctors:
        night_shifts_worked = sum(shifts[(n, d, s)] for d in all_days for s in NIGHT_SHIFT)
        model.add(night_shifts_worked <= max_night_shifts_per_doctor)   

        reward_weight = 10 # Adjust this weight based on how important this rule is to you
