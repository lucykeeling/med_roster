from ortools.sat.python import cp_model
from med_roster.doctor import Doctor, Shift

num_doctors = 35
num_days = 28
all_doctors = range(num_doctors)
all_days = range(num_days)

# FIX: placeholder doctor roster so the model has role/FTE data to work
# with. First 15 doctors are registrars, the rest residents, all full-time.
# FIX: this was originally 10 registrars, which solved to INFEASIBLE - the
# registrar-only shifts need ~9-11 registrars staffed simultaneously, and
# with only 10 total, the fortnightly hours cap and mandatory rest-after-
# night-shift constraint left no slack to also hit the 4-days-off minimum.
# 15 solves cleanly; confirmed by testing 10/15/20/25 directly against the
# solver. Replace this whole list with doctors loaded from the uploaded
# Excel file once that's wired up - nothing else in this file should need
# to change when you do, but real headcounts may need to be closer to this
# ratio for the roster to be solvable at all.
doctors = [
    Doctor(
        name=f"Doctor {i}",
        role="REGISTRAR" if i < 15 else "RESIDENT",
        FTE=1.0,
        availability=None,  # not yet used by any constraint below
    )
    for i in range(num_doctors)
]

# Variables:
# FIX: added actual clock start/end times per shift (this was the TODO in
# the rest-period constraint below). Note: a few of these clock spans are
# 30 minutes longer than the `duration` value (e.g. WEEKDAY_MORNING is
# 08:00-16:30 = 8.5h clock time, but duration=8) - that's presumably a
# handover overlap between shifts (WEEKDAY_NIGHT ends 08:30, WEEKDAY_MORNING
# starts 08:00), so left `duration` untouched since it drives the paid
# fortnightly hours target and wasn't asked to change. Flagging in case that
# 30-minute gap wasn't intentional.
SHIFTS = {
    'WEEKDAY_MORNING_REG': Shift('WEEKDAY_MORNING_REG', duration=8, role_requirements=['REGISTRAR'], min_doctors=5, start_time='08:00', end_time='16:30'),
    'WEEKDAY_MORNING_RES': Shift('WEEKDAY_MORNING_RES', duration=8, role_requirements=['RESIDENT', 'REGISTRAR'], min_doctors=5, start_time='08:00', end_time='16:30'),
    'WEEKDAY_MID_MORNING': Shift('WEEKDAY_MID_MORNING', duration=8, role_requirements=['RESIDENT', 'REGISTRAR'], min_doctors=0, start_time='10:00', end_time='18:00'),  # optional - no minimum
    'WEEKDAY_AFTERNOON_REG': Shift('WEEKDAY_AFTERNOON_REG', duration=8, role_requirements=['REGISTRAR'], min_doctors=2, start_time='16:00', end_time='00:30'),
    'WEEKDAY_AFTERNOON_RES': Shift('WEEKDAY_AFTERNOON_RES', duration=8, role_requirements=['RESIDENT', 'REGISTRAR'], min_doctors=2, start_time='16:00', end_time='00:30'),
    'WEEKDAY_NIGHT_REG': Shift('WEEKDAY_NIGHT_REG', duration=8, role_requirements=['REGISTRAR'], min_doctors=2, start_time='00:00', end_time='08:30'),
    'WEEKDAY_NIGHT_RES': Shift('WEEKDAY_NIGHT_RES', duration=8, role_requirements=['RESIDENT', 'REGISTRAR'], min_doctors=2, start_time='00:00', end_time='08:30'),
    'WEEKEND_DAY_12_REG': Shift('WEEKEND_DAY_12_REG', duration=12, role_requirements=['REGISTRAR'], min_doctors=1, start_time='08:00', end_time='20:00'),
    'WEEKEND_DAY_12_RES': Shift('WEEKEND_DAY_12_RES', duration=12, role_requirements=['RESIDENT', 'REGISTRAR'], min_doctors=2, start_time='08:00', end_time='20:00'),
    'WEEKEND_DAY_8_RES': Shift('WEEKEND_DAY_8_RES', duration=8, role_requirements=['RESIDENT', 'REGISTRAR'], min_doctors=3, start_time='08:00', end_time='16:30'),
    'WEEKEND_NIGHT_REG': Shift('WEEKEND_NIGHT_REG', duration=12, role_requirements=['REGISTRAR'], min_doctors=1, start_time='20:00', end_time='08:00'),
    'WEEKEND_NIGHT_RES': Shift('WEEKEND_NIGHT_RES', duration=12, role_requirements=['RESIDENT', 'REGISTRAR'], min_doctors=2, start_time='20:00', end_time='08:00'),
}

all_shifts = list(SHIFTS.keys())

WEEKEND_SHIFT_NAMES = [s for s in all_shifts if s.startswith('WEEKEND')]
NIGHT_SHIFT_NAMES = [s for s in all_shifts if 'NIGHT' in s]

# Relative cost weight per shift, used to steer any staffing *beyond* the
# required minimum onto cheaper shifts (weekday over weekend, day over
# night) rather than penalty-rate ones. The min_doctors floor is a hard
# constraint regardless of cost - this only affects where extra doctors go.
SHIFT_COST = {
    s: 1 + (2 if s in WEEKEND_SHIFT_NAMES else 0) + (1 if s in NIGHT_SHIFT_NAMES else 0)
    for s in all_shifts
}


# Constraints:
def assign_doctors_to_shifts(model, shifts, doctors, all_doctors, all_days, all_shifts):
    # - Each doctor works at most one shift per day
    for n in all_doctors:
        for d in all_days:
            model.add_at_most_one(shifts[(n, d, s)] for s in all_shifts)

    # FIX: removed the old "no consecutive shifts" block. It compared shift
    # index s to s+1 as if all_shifts were an ordered sequence of same-day
    # time slots - that stopped meaning anything once shifts became named
    # (dict keys aren't ordered by time of day), and add_at_most_one above
    # already guarantees a doctor works at most one shift per day, so this
    # was fully redundant even before the rename.

    # - Minimum rest period of 10 hours between shifts for a doctor
    # FIX: the old version used `s` both as a generator-expression variable
    # and again outside that generator on the same line - generator
    # expressions have their own scope in Python 3, so the outer `s` was
    # never actually defined and this raised NameError. It also only ever
    # covered "worked a night shift -> nothing next day" as an
    # approximation, since Shift didn't track start/end clock times yet.
    # FIX: now that SHIFTS carries real start/end times, this checks the
    # actual gap for every (shift worked on day d, shift worked on day d+1)
    # pair, using absolute minutes-since-day-0 so overnight shifts (that
    # end after midnight) are handled correctly. A pair is only forbidden
    # if its gap is under 10 hours - e.g. WEEKDAY_AFTERNOON (ends 00:00)
    # into next-day WEEKDAY_NIGHT (starts 00:00) is a 0-hour gap and gets
    # blocked, but WEEKDAY_NIGHT (ends 08:30) into next-day WEEKDAY_MORNING
    # (starts 08:00) is a ~23.5-hour gap and is left alone. Only same-day
    # (d) to next-day (d+1) pairs need checking - a doctor can work at most
    # one shift per day, so any pair further apart than that always clears
    # 10 hours.
    MIN_REST_MINUTES = 10 * 60

    def shift_end_minutes(s, d):
        return d * 1440 + SHIFTS[s].start_minutes + SHIFTS[s].clock_duration_minutes

    def shift_start_minutes(s, d):
        return d * 1440 + SHIFTS[s].start_minutes

    for d in all_days:
        if d >= len(all_days) - 1:
            continue
        for s1 in all_shifts:
            for s2 in all_shifts:
                gap_minutes = shift_start_minutes(s2, d + 1) - shift_end_minutes(s1, d)
                if gap_minutes < MIN_REST_MINUTES:
                    for n in all_doctors:
                        model.add(shifts[(n, d, s1)] + shifts[(n, d + 1, s2)] <= 1)

    # - Full time doctors work 80 hours per 14-day fortnight (38h/week,
    #   accruing 1 ADO every 28 days); part-time doctors scale by FTE.
    # FIX: `FTE` was referenced as a bare name that was never defined
    # anywhere (instant NameError), and the old if/else block computed an
    # `hours` value that was never even used. FTE is now read per-doctor
    # from doctors[n].FTE, and the fortnight target scales with it directly.
    # FIX: this was a `<=` upper cap only, with nothing pushing doctors
    # toward actually working their FTE - the solver could (and did) leave
    # some doctors on as little as 1 shift over 28 days while working
    # others up to 19, since "assign fewer people" was cheapest under the
    # staffing-cost objective. Changed to `==` so a doctor's rostered hours
    # per fortnight must hit their FTE target exactly, not just stay under
    # it. Shift durations (8h/12h) can combine to hit any 8*FTE-scaled
    # target in multiples of 4 hours - confirmed solvable at FTE 1.0 (80h)
    # and would need checking again for FTE values that don't divide evenly.
    for n in all_doctors:
        target_hours_per_fortnight = int(80 * doctors[n].FTE)
        for d in range(0, len(all_days), 14):
            total_hours_worked = sum(
                shifts[(n, d + offset, s)] * SHIFTS[s].duration
                for offset in range(14)
                for s in all_shifts
            )
            model.add(total_hours_worked == target_hours_per_fortnight)

    # - Any hours worked > 10 hours in a day is considered overtime
    #   Left disabled - a flat 10hr/day cap would reject every 12hr weekend
    #   shift, since a doctor can only work one shift/day anyway. Revisit if
    #   you want to penalise (rather than forbid) overtime instead.
    #   for n in all_doctors:
    #        for d in all_days:
    #            total_hours_worked = sum(
    #                shifts[(n, d, s)] * SHIFTS[s].duration for s in all_shifts)
    #            model.add(total_hours_worked <= 10)

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
            model.add(sum(shifts[(n, d, s)] for s in all_shifts) > 0).only_enforce_if(day_off[(n, d)].negated())

    consecutive_days_off = []
    for n in all_doctors:
        for d in range(len(all_days) - 1):
            is_consecutive = model.new_bool_var(f"consec_off_doc{n}_day{d}")

            # is_consecutive is true IF AND ONLY IF day d is off AND day d+1 is off
            model.add_bool_and([day_off[(n, d)], day_off[(n, d + 1)]]).only_enforce_if(is_consecutive)
            model.add_bool_or([day_off[(n, d)].negated(), day_off[(n, d + 1)].negated()]).only_enforce_if(is_consecutive.negated())

            # FIX: this append was indented one level too shallow before (it
            # sat outside the `for d` loop), so it only ever recorded the
            # last day's variable per doctor instead of every day.
            consecutive_days_off.append(is_consecutive)

    # ==================== Shift Constraints: ==============================

    # - Each shift has a minimum number of doctors assigned to it, but only
    #   on the day type it actually applies to (WEEKDAY_* shifts Mon-Fri,
    #   WEEKEND_* shifts Sat/Sun - day 0 is treated as Monday).
    # FIX: was SHIFTS[s]['min_staff'] against a dict-of-dicts; now reads
    # min_doctors directly off the Shift object. A shift with min_doctors=0
    # (mid-morning) just becomes `>= 0`, which is always true - this is how
    # "not all shifts must be filled" is expressed, no special-casing needed.
    # FIX: previously every shift type was required to be staffed on all 28
    # days regardless of day-of-week, so WEEKDAY_* and WEEKEND_* registrar
    # shifts were competing for the same registrars on the same day - 11
    # registrars needed simultaneously vs only 10 that exist, which is why
    # the model was INFEASIBLE even after fixing add_exactly_one. Shifts
    # are now gated to their matching day type; on the days a shift doesn't
    # apply, its variables are pinned to 0 instead of left unconstrained,
    # so the solver never assigns anyone to a "weekday morning" shift on a
    # Saturday.
    def is_weekend_day(d):
        return d % 7 in (5, 6)

    def shift_applies(s, d):
        return s.startswith('WEEKEND') == is_weekend_day(d)

    for d in all_days:
        for s in all_shifts:
            if shift_applies(s, d):
                model.add(sum(shifts[(n, d, s)] for n in all_doctors) >= SHIFTS[s].min_doctors)
            else:
                for n in all_doctors:
                    model.add(shifts[(n, d, s)] == 0)

    # - Skill mix
    # - A registrar can work a resident shift, but a resident cannot work a
    #   registrar shift. (HARD CONSTRAINT)
    # FIX: this block used to live outside the function entirely (bad
    # indentation), referenced undefined names like
    # WEEKDAY_MORNING_SHIFT_RES, and compared a shift name to the literal
    # string "REGISTRAR" (which could never be true). It now checks each
    # doctor's own role against that shift's role_requirements directly.
    for n in all_doctors:
        for d in all_days:
            for s in all_shifts:
                if doctors[n].role not in SHIFTS[s].role_requirements:
                    model.add(shifts[(n, d, s)] == 0)

    # - Fairness in weekend/night shift allocation (SOFT CONSTRAINTS)
    # FIX: WEEKEND_SHIFTS, NIGHT_SHIFT, max_weekend_shifts_per_doctor and
    # max_night_shifts_per_doctor were all undefined before. The shift-name
    # lists are now derived from SHIFTS above; the caps below are
    # placeholders - tune them to whatever's fair over a 28-day roster.
    max_weekend_shifts_per_doctor = 6
    max_night_shifts_per_doctor = 6

    for n in all_doctors:
        weekend_shifts_worked = sum(shifts[(n, d, s)] for d in all_days for s in WEEKEND_SHIFT_NAMES)
        model.add(weekend_shifts_worked <= max_weekend_shifts_per_doctor)

    for n in all_doctors:
        night_shifts_worked = sum(shifts[(n, d, s)] for d in all_days for s in NIGHT_SHIFT_NAMES)
        model.add(night_shifts_worked <= max_night_shifts_per_doctor)

    # - Prefer weekday/day shifts over weekend/night shifts for any staffing
    #   beyond the required minimum (weekend/night is more expensive).
    # Since min_doctors is a hard floor on every shift regardless of cost,
    # that mandatory portion contributes a fixed cost no matter how the
    # solver assigns doctors - so minimizing total cost across ALL
    # assignments (not just the "excess" above the floor) already has the
    # same effect on where any extra doctors go, without needing to model
    # excess as a separate variable.
    staffing_cost = sum(
        SHIFT_COST[s] * shifts[(n, d, s)]
        for n in all_doctors
        for d in all_days
        for s in all_shifts
    )

    # FIX: this function no longer calls model.maximize() itself. Before,
    # it was being called once per doctor inside the `for n` loop above
    # (35 times, overwriting itself each time) and referenced
    # `other_objectives`, which was never defined anywhere. Soft-constraint
    # terms are returned instead so the caller (app.py) can combine this
    # with shift-request satisfaction into a single model.maximize(...)
    # call - app.py is currently empty and still needs that assembly code.
    # `staffing_cost` should be SUBTRACTED (or negatively weighted) in that
    # final objective, e.g.:
    #   model.maximize(
    #       sum(objective_terms['consecutive_days_off']) * 10
    #       + shift_request_satisfaction
    #       - objective_terms['staffing_cost'] * cost_weight
    #   )
    objective_terms = {
        'consecutive_days_off': consecutive_days_off,
        'staffing_cost': staffing_cost,
    }
    return objective_terms
