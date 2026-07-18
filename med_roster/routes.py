from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import Staff

router = APIRouter()

@router.get("/roster/{roster_id}")
def read_roster(roster_id: str):
    return {"message": f"Hello from roster {roster_id}!"}


@router.get("/staff")
def list_staff(db: Session = Depends(get_db)):
    return db.query(Staff).all()

