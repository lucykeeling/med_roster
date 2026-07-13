from typing import Union
from ortools.sat.python import cp_model

num_nurses = 5
num_shifts = 3
num_days = 7
all_nurses = range(num_nurses)
all_shifts = range(num_shifts)
all_days = range(num_days)
shift_requests = [
    [[0, 0, 1], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 1], [0, 1, 0], [0, 0, 1]],
    [[0, 0, 0], [0, 0, 0], [0, 1, 0], [0, 1, 0], [1, 0, 0], [0, 0, 0], [0, 0, 1]],
    [[0, 1, 0], [0, 1, 0], [0, 0, 0], [1, 0, 0], [0, 0, 0], [0, 1, 0], [0, 0, 0]],
    [[0, 0, 1], [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 0], [1, 0, 0], [0, 0, 0]],
    [[0, 0, 0], [0, 0, 1], [0, 1, 0], [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 0]],
]

#Model:
model = cp_model.CpModel()

#Variables:
shifts = {}
for n in all_nurses:
    for d in all_days:
        for s in all_shifts:
            shifts[(n, d, s)] = model.new_bool_var(f'shift_n{n}_d{d}_s{s}') 

#Constraints:
for d in all_days:
    for s in all_shifts:
        model.add_exactly_one(shifts[(n, d, s)] for n in all_nurses)    

for n in all_nurses:
    for d in all_days:
        model.add_at_most_one(shifts[(n, d, s)] for s in all_shifts)

# distribute shifts evenly among nurses
min_shifts_per_nurse = (num_shifts * num_days) // num_nurses
if num_shifts * num_days % num_nurses == 0:
    max_shifts_per_nurse = min_shifts_per_nurse
else:
    max_shifts_per_nurse = min_shifts_per_nurse + 1
for n in all_nurses:
    num_shifts_worked: Union[cp_model.LinearExpr, int] = 0
    for d in all_days:
        for s in all_shifts:
            num_shifts_worked += shifts[(n, d, s)]
    model.add(min_shifts_per_nurse <= num_shifts_worked)
    model.add(num_shifts_worked <= max_shifts_per_nurse)


model.maximize(
    sum(
        shift_requests[n][d][s] * shifts[(n, d, s)]
        for n in all_nurses
        for d in all_days
        for s in all_shifts
    )
)

solver = cp_model.CpSolver()
status = solver.Solve(model)

#Finding the optimal schedule:

if status == cp_model.OPTIMAL:
    print("Solution:")
    for d in all_days:
        print(f"Day {d}:")
        for n in all_nurses:
            for s in all_shifts:
                if solver.value(shifts[(n, d, s)]) ==1:
                    if shift_requests[n][d][s] == 1:
                        print(f"  Nurse {n} works shift {s} (requested)")
                    else:
                        print(f"  Nurse {n} works shift {s} (not requested)")
        print()
    print(
        f"Number of shift requests met = {solver.objective_value} out of {num_nurses * num_days}")
else:
    print("No optimal solution found.")

#Statistics:
print("\nStatistics")
print(f" - Conflicts: {solver.NumConflicts()}")
print(f" - Branches: {solver.NumBranches()}")   
print(f" - Wall time: {solver.WallTime()} s")

