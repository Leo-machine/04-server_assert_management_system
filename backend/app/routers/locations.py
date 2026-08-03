from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from .. import enums
from ..deps import get_current_user, require_role
from ..models import User
from ..schemas import (
    LocationDistributionOut,
    StorageLocationIn,
    StorageLocationOut,
    StorageLocationUpdateIn,
)
from ..services.movement import BusinessError
from ..services import locations as locations_service

router = APIRouter(prefix="/storage-locations", tags=["storage-locations"])


@router.get("", response_model=list[StorageLocationOut])
def list_locations(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return locations_service.list_locations(db, category=category)


@router.get("/distribution", response_model=list[LocationDistributionOut])
def distribution(db: Session = Depends(get_db)):
    return locations_service.location_distribution(db)


@router.post("", response_model=StorageLocationOut)
def create_location(
    body: StorageLocationIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_ADMIN,))
    try:
        return locations_service.create_location(db, **body.model_dump())
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.put("/{location_id}", response_model=StorageLocationOut)
def update_location(
    location_id: int,
    body: StorageLocationUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_ADMIN,))
    try:
        return locations_service.update_location(
            db, location_id, **body.model_dump(exclude_unset=True)
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.delete("/{location_id}")
def delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_ADMIN,))
    try:
        locations_service.delete_location(db, location_id)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    return {"ok": True}
