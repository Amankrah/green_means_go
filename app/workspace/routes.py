"""
workspace/routes.py — the authenticated user's own records: the farms and facilities
they manage, plus a unified list of their saved assessments for dashboards.

Farms are managed by farmers (their own) and extension officers (one per client farm).
Facilities are managed by processors. Researchers manage both. Everything here is scoped
to the current user; there is no cross-user visibility.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import Facility, Farm, User, UserRole
from auth.deps import get_current_user, require_role
from store import delete_owned_assessment, get_owned_assessment, list_owned_assessments

router = APIRouter(tags=["workspace"])

# Only owners keep a farm/facility registry. Extension officers and researchers are
# external agents: they run assessments (filling the wizard) but do not create or
# manage Farm / Facility records on behalf of others.
_farm_roles = require_role(UserRole.farmer)
_facility_roles = require_role(UserRole.processor)


# --- schemas ---------------------------------------------------------------------

class FarmCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    country: Optional[str] = Field(default=None, max_length=64)
    region: Optional[str] = Field(default=None, max_length=64)
    location: Optional[str] = Field(default=None, max_length=255)
    size_ha: Optional[float] = None
    notes: Optional[str] = None
    farmer_name: Optional[str] = Field(default=None, max_length=255)
    farmer_contact: Optional[str] = Field(default=None, max_length=255)


class FarmUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    country: Optional[str] = Field(default=None, max_length=64)
    region: Optional[str] = Field(default=None, max_length=64)
    location: Optional[str] = Field(default=None, max_length=255)
    size_ha: Optional[float] = None
    notes: Optional[str] = None
    farmer_name: Optional[str] = Field(default=None, max_length=255)
    farmer_contact: Optional[str] = Field(default=None, max_length=255)


class FarmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    country: Optional[str] = None
    region: Optional[str] = None
    location: Optional[str] = None
    size_ha: Optional[float] = None
    notes: Optional[str] = None
    farmer_name: Optional[str] = None
    farmer_contact: Optional[str] = None
    created_at: datetime


class FacilityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    facility_type: Optional[str] = Field(default=None, max_length=64)
    country: Optional[str] = Field(default=None, max_length=64)
    region: Optional[str] = Field(default=None, max_length=64)
    location: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None


class FacilityUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    facility_type: Optional[str] = Field(default=None, max_length=64)
    country: Optional[str] = Field(default=None, max_length=64)
    region: Optional[str] = Field(default=None, max_length=64)
    location: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None


class FacilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    facility_type: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


# --- farms -----------------------------------------------------------------------

@router.post("/farms", response_model=FarmOut, status_code=status.HTTP_201_CREATED)
def create_farm(payload: FarmCreate, user: User = Depends(_farm_roles), db: Session = Depends(get_db)):
    farm = Farm(created_by_user_id=user.id, **payload.model_dump())
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


@router.get("/farms", response_model=list[FarmOut])
def list_farms(user: User = Depends(_farm_roles), db: Session = Depends(get_db)):
    stmt = select(Farm).where(Farm.created_by_user_id == user.id).order_by(Farm.created_at.desc())
    return list(db.scalars(stmt))


def _owned_farm(farm_id: str, user: User, db: Session) -> Farm:
    farm = db.get(Farm, farm_id)
    if farm is None or farm.created_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm


@router.get("/farms/{farm_id}", response_model=FarmOut)
def get_farm(farm_id: str, user: User = Depends(_farm_roles), db: Session = Depends(get_db)):
    return _owned_farm(farm_id, user, db)


@router.patch("/farms/{farm_id}", response_model=FarmOut)
def update_farm(farm_id: str, payload: FarmUpdate, user: User = Depends(_farm_roles), db: Session = Depends(get_db)):
    farm = _owned_farm(farm_id, user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(farm, field, value)
    db.commit()
    db.refresh(farm)
    return farm


@router.delete("/farms/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_farm(farm_id: str, user: User = Depends(_farm_roles), db: Session = Depends(get_db)):
    farm = _owned_farm(farm_id, user, db)
    db.delete(farm)
    db.commit()


# --- facilities ------------------------------------------------------------------

@router.post("/facilities", response_model=FacilityOut, status_code=status.HTTP_201_CREATED)
def create_facility(payload: FacilityCreate, user: User = Depends(_facility_roles), db: Session = Depends(get_db)):
    facility = Facility(created_by_user_id=user.id, **payload.model_dump())
    db.add(facility)
    db.commit()
    db.refresh(facility)
    return facility


@router.get("/facilities", response_model=list[FacilityOut])
def list_facilities(user: User = Depends(_facility_roles), db: Session = Depends(get_db)):
    stmt = select(Facility).where(Facility.created_by_user_id == user.id).order_by(Facility.created_at.desc())
    return list(db.scalars(stmt))


def _owned_facility(facility_id: str, user: User, db: Session) -> Facility:
    facility = db.get(Facility, facility_id)
    if facility is None or facility.created_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Facility not found")
    return facility


@router.get("/facilities/{facility_id}", response_model=FacilityOut)
def get_facility(facility_id: str, user: User = Depends(_facility_roles), db: Session = Depends(get_db)):
    return _owned_facility(facility_id, user, db)


@router.patch("/facilities/{facility_id}", response_model=FacilityOut)
def update_facility(facility_id: str, payload: FacilityUpdate, user: User = Depends(_facility_roles), db: Session = Depends(get_db)):
    facility = _owned_facility(facility_id, user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(facility, field, value)
    db.commit()
    db.refresh(facility)
    return facility


@router.delete("/facilities/{facility_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_facility(facility_id: str, user: User = Depends(_facility_roles), db: Session = Depends(get_db)):
    facility = _owned_facility(facility_id, user, db)
    db.delete(facility)
    db.commit()


# --- unified saved-assessment list (for dashboards) -------------------------------

@router.get("/me/assessments")
def my_assessments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Every saved assessment the current user owns, farm and processing alike, newest
    first — the backing list for the dashboard."""
    rows = list_owned_assessments(db, user)
    return {
        "assessments": [
            {
                "id": row.id,
                "type": row.type.value if hasattr(row.type, "value") else str(row.type),
                "title": row.title,
                "company_name": row.company_name,
                "country": row.country,
                "region": row.region,
                "farm_id": row.farm_id,
                "facility_id": row.facility_id,
                "single_score": row.single_score,
                "status": row.status,
                "assessment_date": row.payload_json.get("assessment_date"),
                "created_at": row.created_at,
                "can_rerun": bool(
                    row.request_json and row.request_json.get("form")
                ),
            }
            for row in rows
        ],
        "total": len(rows),
    }


@router.get("/me/assessments/{assessment_id}/request")
def get_assessment_request(
    assessment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the stored submit payload so the owner can edit inputs and re-run."""
    row = get_owned_assessment(db, user, assessment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if not row.request_json:
        raise HTTPException(
            status_code=409,
            detail=(
                "This assessment was saved before edit/re-run support. "
                "Run a new assessment instead, or delete this one."
            ),
        )
    return {
        "id": row.id,
        "type": row.type.value if hasattr(row.type, "value") else str(row.type),
        "title": row.title,
        "farm_id": row.farm_id,
        "facility_id": row.facility_id,
        "api": row.request_json.get("api"),
        "form": row.request_json.get("form"),
    }


@router.delete("/me/assessments/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(
    assessment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permanently delete one of the current user's assessments. Not owned → 404."""
    if not delete_owned_assessment(db, user, assessment_id):
        raise HTTPException(status_code=404, detail="Assessment not found")
