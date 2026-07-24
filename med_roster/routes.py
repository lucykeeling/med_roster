from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import Staff
from fastapi import HTTPException, status
from schemas import StaffCreate, StaffRead

router = APIRouter()

@router.get("/roster/{roster_id}")
def read_roster(roster_id: str):
    return {"message": f"Hello from roster {roster_id}!"}

@router.get("/staff", response_model=list[StaffRead])
def list_staff(db: Session = Depends(get_db)):
    return db.query(Staff).all()

@router.post("/staff", response_model=StaffRead, status_code=status.HTTP_201_CREATED)
def create_staff(payload: StaffCreate, db: Session = Depends(get_db)):
    staff = Staff(**payload.model_dump())
    db.add(staff)          # stage it
    db.commit()            # write it — nothing is saved until this line
    db.refresh(staff)      # re-read, to pick up the DB-generated staff_id
    return staff


@router.get("/staff/{staff_id}", response_model=StaffRead)
def get_staff(staff_id: int, db: Session = Depends(get_db)):
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise HTTPException(status_code=404, detail=f"No staff with id {staff_id}")
    return staff
