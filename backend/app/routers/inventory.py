from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import enums
from ..database import get_db
from ..deps import get_current_user, require_role
from ..models import User
from ..schemas import AllocatableOverviewOut, AllocatableSummaryItem
from ..services import inventory as inventory_service

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/allocatable-summary", response_model=list[AllocatableSummaryItem])
def allocatable_summary(
    category: Optional[str] = Query(None, description="品类过滤，如 内存"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.INVENTORY_ROLES)
    return inventory_service.allocatable_summary(db, category=category)


@router.get("/allocatable-overview", response_model=AllocatableOverviewOut)
def allocatable_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.INVENTORY_ROLES)
    return inventory_service.allocatable_overview(db)
