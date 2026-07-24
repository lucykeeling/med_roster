from pydantic import BaseModel


class StaffCreate(BaseModel):
    """What a client must send to create a staff member."""
    name: str
    employment_fraction: float | None = None
    classification: str | None = None


class StaffRead(BaseModel):
    """What we send back. Explicit — adding a DB column won't leak it."""
    staff_id: int
    name: str
    employment_fraction: float | None
    classification: str | None

    model_config = {"from_attributes": True}
