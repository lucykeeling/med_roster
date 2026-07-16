from typing import Union
from ortools.sat.python import cp_model
from .constraints import assign_doctors_to_shifts


#Hardcoded example data for testing purposes
num_doctors = 5
num_shifts = 3
num_days = 7
all_doctors = range(num_doctors)
all_shifts = range(num_shifts)
all_days = range(num_days)
shift_requests = [
    [[0, 0, 1], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 1], [0, 1, 0], [0, 0, 1]],
    [[0, 0, 0], [0, 0, 0], [0, 1, 0], [0, 1, 0], [1, 0, 0], [0, 0, 0], [0, 0, 1]],
    [[0, 1, 0], [0, 1, 0], [0, 0, 0], [1, 0, 0], [0, 0, 0], [0, 1, 0], [0, 0, 0]],
    [[0, 0, 1], [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 0], [1, 0, 0], [0, 0, 0]],
    [[0, 0, 0], [0, 0, 1], [0, 1, 0], [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 0]],


# Model:
model = cp_model.CpModel()

#Variables:
shifts = {}
for n in all_doctors:
    for d in all_days:
        for s in all_shifts:
            shifts[(n, d, s)] = model.new_bool_var(f'shift_n{n}_d{d}_s{s}') 


model.maximize(
    sum(
        shift_requests[n][d][s] * shifts[(n, d, s)] * reward_weight
        for n in all_doctors      
        for d in all_days
        for s in all_shifts
    )
)

assign_doctors_to_shifts(model, shifts, all_doctors, all_days, all_shifts)
solver = cp_model.CpSolver()
status = solver.Solve(model)



#Finding the optimal schedule:

if status == cp_model.OPTIMAL:
    print("Solution:")
    for d in all_days:
        print(f"Day {d}:")
        for n in all_doctors:
            for s in all_shifts:
                if solver.value(shifts[(n, d, s)]) ==1:
                    if shift_requests[n][d][s] == 1:
                        print(f"  Doctor {n} works shift {s} (requested)")
                    else:
                        print(f"  Doctor {n} works shift {s} (not requested)")
        print()
    print(
        f"Number of shift requests met = {solver.objective_value} out of {num_doctors * num_days}")
else:
    print("No optimal solution found.")

#Statistics:
print("\nStatistics")
print(f" - Conflicts: {solver.NumConflicts()}")
print(f" - Branches: {solver.NumBranches()}")   
print(f" - Wall time: {solver.WallTime()} s")