from ortools.sat.python import cp_model

from constraints.med_constraints import (
    all_days,
    all_doctors,
    all_shifts,
    assign_doctors_to_shifts,
    doctors,
)

model = cp_model.CpModel()

shifts = {
    (n, d, s): model.new_bool_var(f"shift_doc{n}_day{d}_{s}")
    for n in all_doctors
    for d in all_days
    for s in all_shifts
}

objective_terms = assign_doctors_to_shifts(
    model, shifts, doctors, all_doctors, all_days, all_shifts
)

# Weights are placeholders - tune once the roster is actually reviewed by a
# human scheduler. staffing_cost is subtracted since cheaper (weekday/day)
# shifts should be preferred for any staffing beyond the required minimum.
CONSECUTIVE_DAYS_OFF_WEIGHT = 10
STAFFING_COST_WEIGHT = 1

model.maximize(
    sum(objective_terms["consecutive_days_off"]) * CONSECUTIVE_DAYS_OFF_WEIGHT
    - objective_terms["staffing_cost"] * STAFFING_COST_WEIGHT
)

solver = cp_model.CpSolver()
status = solver.solve(model)

if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    print("Solution:" if status == cp_model.OPTIMAL else "Feasible (not proven optimal):")
    for d in all_days:
        print(f"Day {d}:")
        for n in all_doctors:
            worked = [s for s in all_shifts if solver.value(shifts[(n, d, s)]) == 1]
            if worked:
                print(f"  {doctors[n].name} ({doctors[n].role}): {worked[0]}")
        print()
else:
    print("No feasible solution found.")

print("\nStatistics")
print(f" - Conflicts: {solver.num_conflicts()}")
print(f" - Branches: {solver.num_branches()}")
print(f" - Wall time: {solver.wall_time()} s")
