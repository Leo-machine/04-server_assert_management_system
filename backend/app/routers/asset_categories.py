from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import enums
from ..database import get_db
from ..deps import get_current_user, require_role
from ..models import User
from ..schemas import AssetCategoryIn, AssetCategoryOut, AssetCategoryUpdateIn
from ..services import asset_categories as service
from ..services.movement import BusinessError

router = APIRouter(prefix="/asset-categories", tags=["asset-categories"])


@router.get("", response_model=list[AssetCategoryOut])
def list_asset_categories(
    tree: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_categories(db, tree=tree)


@router.post("", response_model=AssetCategoryOut)
def create_asset_category(
    body: AssetCategoryIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    try:
        return service.create_category(db, **body.model_dump())
    except BusinessError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.put("/{category_id}", response_model=AssetCategoryOut)
def update_asset_category(
    category_id: int,
    body: AssetCategoryUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    try:
        return service.update_category(db, category_id, **body.model_dump())
    except BusinessError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.delete("/{category_id}")
def delete_asset_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    try:
        service.delete_category(db, category_id)
    except BusinessError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return {"ok": True}
