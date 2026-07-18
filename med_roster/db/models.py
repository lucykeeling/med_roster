import datetime

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class Staff(Base):
    __tablename__ = "staff"

    staff_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    employment_fraction: Mapped[float | None]
    classification: Mapped[str | None]

    skills: Mapped[list["StaffSkill"]] = relationship(back_populates="staff")


class StaffSkill(Base):
    __tablename__ = "staff_skill"

    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.staff_id", ondelete="CASCADE"), primary_key=True
    )
    skill: Mapped[str] = mapped_column(primary_key=True)

    staff: Mapped["Staff"] = relationship(back_populates="skills")


class Ward(Base):
    __tablename__ = "ward"

    ward_id: Mapped[int] = mapped_column(primary_key=True)
    ward_name: Mapped[str] = mapped_column(unique=True, nullable=False)
    shift_structure: Mapped[str | None]

    demand_templates: Mapped[list["DemandTemplate"]] = relationship(back_populates="ward")


class DemandTemplate(Base):
    __tablename__ = "demand_template"

    demand_template_id: Mapped[int] = mapped_column(primary_key=True)
    ward_id: Mapped[int] = mapped_column(
        ForeignKey("ward.ward_id", ondelete="CASCADE"), nullable=False
    )
    day: Mapped[str | None]
    shift: Mapped[str | None]
    minimum_staff_count: Mapped[int | None]

    ward: Mapped["Ward"] = relationship(back_populates="demand_templates")
    skill_requirements: Mapped[list["DemandTemplateSkillRequirement"]] = relationship(
        back_populates="demand_template"
    )


class DemandTemplateSkillRequirement(Base):
    __tablename__ = "demand_template_skill_requirement"

    demand_template_id: Mapped[int] = mapped_column(
        ForeignKey("demand_template.demand_template_id", ondelete="CASCADE"),
        primary_key=True,
    )
    classification: Mapped[str] = mapped_column(primary_key=True)
    minimum_count: Mapped[int] = mapped_column(nullable=False)

    demand_template: Mapped["DemandTemplate"] = relationship(
        back_populates="skill_requirements"
    )


class RosterPeriod(Base):
    __tablename__ = "roster_period"

    roster_period_id: Mapped[int] = mapped_column(primary_key=True)
    ward_id: Mapped[int] = mapped_column(
        ForeignKey("ward.ward_id", ondelete="CASCADE"), nullable=False
    )
    start_date: Mapped[datetime.date] = mapped_column(nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="draft")


class Request(Base):
    __tablename__ = "request"

    request_id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.staff_id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[datetime.date | None]
    request_type: Mapped[str | None]
    approved: Mapped[bool | None]


class Assignment(Base):
    __tablename__ = "assignment"
    __table_args__ = (
        UniqueConstraint("staff_id", "date"),
        CheckConstraint("source IN ('solver', 'manual')"),
    )

    assignment_id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.staff_id", ondelete="CASCADE"), nullable=False
    )
    roster_period_id: Mapped[int] = mapped_column(
        ForeignKey("roster_period.roster_period_id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[datetime.date] = mapped_column(nullable=False)
    shift: Mapped[str] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(nullable=False, default="solver")
