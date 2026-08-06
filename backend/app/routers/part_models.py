from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..category_specs import categories_schema
from ..database import get_db
from .. import enums
from ..deps import get_current_user, require_role
from ..models import User
from ..schemas import (
    CategorySchemaOut,
    PartModelIn,
    PartModelOut,
    PartModelUpdateIn,
)
from ..services.movement import BusinessError
from ..services import part_models as part_models_service

router = APIRouter(tags=["part-models"])


@router.get("/categories", response_model=list[CategorySchemaOut])
def list_categories():
    return categories_schema()


@router.get("/part-models", response_model=list[PartModelOut])
def list_part_models(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return part_models_service.list_models(db, category=category)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.get("/part-models/{model_id}", response_model=PartModelOut)
def get_part_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return part_models_service.get_model(db, model_id)
    except BusinessError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@router.post("/part-models", response_model=PartModelOut)
def create_part_model(
    body: PartModelIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    try:
        return part_models_service.create_model(db, **body.model_dump())
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.put("/part-models/{model_id}", response_model=PartModelOut)
def update_part_model(
    model_id: int,
    body: PartModelUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    try:
        return part_models_service.update_model(
            db, model_id, **body.model_dump(exclude_unset=True)
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.delete("/part-models/{model_id}")
def delete_part_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    try:
        part_models_service.delete_model(db, model_id)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    return {"ok": True}
