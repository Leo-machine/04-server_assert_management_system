from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_operator_id, require_user
from ..schemas import BrandIn, BrandOut, BrandUpdateIn
from ..services.movement import BusinessError
from ..services import brands as brands_service

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("", response_model=list[BrandOut])
def list_brands(
    category: Optional[str] = Query(None, description="按配件类型过滤，如 内存"),
    db: Session = Depends(get_db),
):
    try:
        return brands_service.list_brands(db, category=category)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.post("", response_model=BrandOut)
def create_brand(
    body: BrandIn,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    require_user(db, operator_id)
    try:
        return brands_service.create_brand(
            db, name=body.name, categories=body.categories
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.put("/{brand_id}", response_model=BrandOut)
def update_brand(
    brand_id: int,
    body: BrandUpdateIn,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    require_user(db, operator_id)
    payload = body.model_dump(exclude_unset=True)
    try:
        return brands_service.update_brand(
            db,
            brand_id,
            name=payload.get("name"),
            categories=payload.get("categories"),
            set_categories="categories" in payload,
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.delete("/{brand_id}")
def delete_brand(
    brand_id: int,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    require_user(db, operator_id)
    try:
        brands_service.delete_brand(db, brand_id)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    return {"ok": True}
