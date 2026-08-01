from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import AllocatableSummaryItem
from ..services import inventory as inventory_service

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/allocatable-summary", response_model=list[AllocatableSummaryItem])
def allocatable_summary(
    category: Optional[str] = Query(None, description="品类过滤，如 内存"),
    db: Session = Depends(get_db),
):
    try:
        return inventory_service.allocatable_summary(db, category=category)
    except Exception as e:  # noqa: BLE001 — 保持只读接口稳妥
        raise HTTPException(status_code=400, detail=str(e)) from e
