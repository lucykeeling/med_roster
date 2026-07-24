from ortools.sat.python import cp_model

from constraints.med_constraints import assign_doctors_to_shifts
from doctor import Doctor

CONSECUTIVE_DAYS_OFF_WEIGHT = 10
SHIFT_REQUEST_WEIGHT = 5
STAFFING_COST_WEIGHT = 1


def solve_roster(
    doctors: list[Doctor],
    num_days: int = 28,
    time_limit_s: float = 60.0,
    requests: dict[tuple[int, int], str] | None = None,
    start_weekday: int = 0,
):
    """Build and solve a roster for real doctors. Returns a list of assignments.

    `requests` maps (doctor_index, day_index) -> 'DAY' | 'NIGHT' | 'OFF', built
    from the uploaded spreadsheet's request rows (see the note in the module
    docstring / README on constructing it). `start_weekday` is the weekday of
    day 0 (0 = Monday); pass the roster period's real start weekday so the
    solver's weekend detection matches the sheet's calendar dates.
    """
    from constraints.med_constraints import all_shifts

    all_doctors = range(len(doctors))
    all_days = range(num_days)

    model = cp_model.CpModel()
    shifts = {
        (n, d, s): model.new_bool_var(f"shift_doc{n}_day{d}_{s}")
        for n in all_doctors
        for d in all_days
        for s in all_shifts
    }

    objective_terms = assign_doctors_to_shifts(
        model, shifts, doctors, all_doctors, all_days, all_shifts,
        requests=requests, start_weekday=start_weekday,
    )

    model.maximize(
        sum(objective_terms["consecutive_days_off"]) * CONSECUTIVE_DAYS_OFF_WEIGHT
        + sum(objective_terms["shift_request_satisfaction"]) * SHIFT_REQUEST_WEIGHT
        - objective_terms["staffing_cost"] * STAFFING_COST_WEIGHT
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None  # infeasible — no roster satisfies every hard constraint

    return [
        {"doctor_index": n, "name": doctors[n].name, "day": d, "shift": s}
        for n in all_doctors
        for d in all_days
        for s in all_shifts
        if solver.value(shifts[(n, d, s)]) == 1
    ]
