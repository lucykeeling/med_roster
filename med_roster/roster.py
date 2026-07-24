"""Solve a roster from the database and write the result into `assignment`.

This is the bridge between the data your spreadsheet upload produces (staff rows
+ per-day request rows) and the CP-SAT solver in `solver.py`. The flow is:

    staff + requests (DB)  ->  Doctor objects + request index  ->  solve_roster
        ->  assignment rows (DB)

The solver works in integer day indices (0..num_days-1); the database works in
real dates. `start_date` is what ties the two together, so it must be the first
day of the roster period (the first date column of the uploaded sheet).
"""

import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func
from sqlalchemy.orm import Session

from constraints.med_constraints import DAY_SHIFT_NAMES, NIGHT_SHIFT_NAMES
from db.database import get_db
from db.models import Assignment, Request, RosterPeriod, Staff, Ward
from doctor import Doctor
from solver import solve_roster

router = APIRouter()

SOLVER_ROLES = ["REGISTRAR", "RESIDENT"]
DEFAULT_WARD_NAME = "Default Ward"


def staff_to_doctors(db: Session) -> tuple[list[Doctor], list[int]]:
    """Load rosterable staff as Doctor objects.

    Returns the doctors and a parallel list mapping each doctor's index back to
    its staff_id — the solver only knows indices, so we need this to write
    assignments back. `classification` flows straight through as `role`; the
    upload already stored it uppercased to match the solver's role_requirements.
    """
    rows = (
        db.query(Staff)
        .filter(Staff.classification.in_(SOLVER_ROLES))
        .order_by(Staff.staff_id)
        .all()
    )
    doctors = [
        Doctor(
            name=r.name,
            role=r.classification,
            FTE=r.employment_fraction or 1.0,
            availability=None,
        )
        for r in rows
    ]
    staff_ids_by_index = [r.staff_id for r in rows]
    return doctors, staff_ids_by_index


def build_request_index(
    db: Session,
    staff_ids_by_index: list[int],
    start_date: datetime.date,
    num_days: int,
) -> dict[tuple[int, int], str]:
    """Turn stored request rows into the (doctor_index, day_index) -> code map.

    Requests whose date falls outside the [start_date, start_date+num_days)
    window, or whose staff member isn't being rostered, are skipped.
    """
    index_of_staff = {staff_id: i for i, staff_id in enumerate(staff_ids_by_index)}
    requests: dict[tuple[int, int], str] = {}
    for r in db.query(Request).all():
        if r.date is None or r.request_type is None:
            continue
        if r.staff_id not in index_of_staff:
            continue
        day = (r.date - start_date).days
        if 0 <= day < num_days:
            requests[(index_of_staff[r.staff_id], day)] = r.request_type
    return requests


def _get_or_create_ward(db: Session, ward_name: str) -> Ward:
    ward = db.query(Ward).filter(Ward.ward_name == ward_name).one_or_none()
    if ward is None:
        ward = Ward(ward_name=ward_name)
        db.add(ward)
        db.flush()  # assign ward_id
    return ward


def _get_or_create_period(
    db: Session,
    ward_id: int,
    start_date: datetime.date,
    end_date: datetime.date,
) -> RosterPeriod:
    period = (
        db.query(RosterPeriod)
        .filter(
            RosterPeriod.ward_id == ward_id,
            RosterPeriod.start_date == start_date,
            RosterPeriod.end_date == end_date,
        )
        .one_or_none()
    )
    if period is None:
        period = RosterPeriod(
            ward_id=ward_id,
            start_date=start_date,
            end_date=end_date,
            status="draft",
        )
        db.add(period)
        db.flush()  # assign roster_period_id
    return period


def _count_honoured(
    requests: dict[tuple[int, int], str],
    worked: dict[tuple[int, int], str],
) -> dict[str, dict[str, int]]:
    """Compare requests against the solved roster, per request type."""
    stats = {code: {"requested": 0, "honoured": 0} for code in ("DAY", "NIGHT", "OFF")}
    for key, code in requests.items():
        if code not in stats:
            continue
        stats[code]["requested"] += 1
        shift = worked.get(key)
        honoured = (
            (code == "OFF" and shift is None)
            or (code == "DAY" and shift in DAY_SHIFT_NAMES)
            or (code == "NIGHT" and shift in NIGHT_SHIFT_NAMES)
        )
        if honoured:
            stats[code]["honoured"] += 1
    return stats


@router.post("/roster/solve")
def solve(
    start_date: datetime.date | None = None,
    num_days: int = 28,
    ward_name: str = DEFAULT_WARD_NAME,
    time_limit_s: float = 30.0,
    db: Session = Depends(get_db),
):
    """Build a roster from the staff + requests in the database and save it.

    `start_date` defaults to the earliest request on file. `num_days` must be a
    multiple of 14 (the solver's fortnight logic requires whole fortnights);
    leave it at 28 to match the 4-week upload.
    """
    if num_days <= 0 or num_days % 14 != 0:
        raise HTTPException(
            400,
            f"num_days must be a positive multiple of 14 (got {num_days}). "
            "Use 28 to match a 4-week upload.",
        )

    if start_date is None:
        start_date = db.query(func.min(Request.date)).scalar()
        if start_date is None:
            raise HTTPException(
                400,
                "No requests in the database and no start_date given — upload a "
                "roster-request sheet first, or pass ?start_date=YYYY-MM-DD.",
            )

    doctors, staff_ids_by_index = staff_to_doctors(db)
    if not doctors:
        raise HTTPException(
            400,
            "No staff classified REGISTRAR or RESIDENT to roster. Upload staff "
            "first.",
        )

    requests = build_request_index(db, staff_ids_by_index, start_date, num_days)
    end_date = start_date + datetime.timedelta(days=num_days - 1)

    ward = _get_or_create_ward(db, ward_name)
    period = _get_or_create_period(db, ward.ward_id, start_date, end_date)
    period.status = "solving"
    db.commit()

    result = solve_roster(
        doctors,
        num_days=num_days,
        time_limit_s=time_limit_s,
        requests=requests,
        start_weekday=start_date.weekday(),
    )

    if result is None:
        period.status = "infeasible"
        db.commit()
        raise HTTPException(
            422,
            "No feasible roster — the hard constraints conflict. Usually too few "
            "staff for the minimum staffing levels; try adding doctors (the "
            "solver needs roughly 15 registrars) or relaxing a constraint.",
        )

    # Replace any previous solve for this period so re-running is idempotent.
    db.execute(delete(Assignment).where(Assignment.roster_period_id == period.roster_period_id))

    worked: dict[tuple[int, int], str] = {}
    new_assignments = []
    for a in result:
        n, day, shift = a["doctor_index"], a["day"], a["shift"]
        worked[(n, day)] = shift
        new_assignments.append(
            Assignment(
                staff_id=staff_ids_by_index[n],
                roster_period_id=period.roster_period_id,
                date=start_date + datetime.timedelta(days=day),
                shift=shift,
                source="solver",
            )
        )
    db.add_all(new_assignments)
    period.status = "solved"
    db.commit()

    honoured = _count_honoured(requests, worked)
    total_requested = sum(v["requested"] for v in honoured.values())
    total_honoured = sum(v["honoured"] for v in honoured.values())

    return {
        "roster_period_id": period.roster_period_id,
        "ward": ward_name,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "num_days": num_days,
        "status": period.status,
        "doctors_rostered": len(doctors),
        "assignments_written": len(new_assignments),
        "requests": {
            "total": total_requested,
            "honoured": total_honoured,
            "by_type": honoured,
        },
    }
