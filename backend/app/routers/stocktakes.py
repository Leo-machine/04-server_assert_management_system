from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import enums
from ..deps import get_current_user, require_role
from ..models import User
from ..schemas import (
    StocktakeCheckIn,
    StocktakeConfirmExternalIn,
    StocktakeCreateIn,
    StocktakeDiscrepancyOut,
    StocktakeItemOut,
    StocktakeListOut,
    StocktakeOut,
)
from ..services.movement import BusinessError
from ..services import stocktake as stocktake_service

router = APIRouter(prefix="/stocktakes", tags=["stocktakes"])


def _item_out(item) -> StocktakeItemOut:
    data = StocktakeItemOut.model_validate(item)
    data.expected_status_derived = stocktake_service.derived_status_from_loc(
        item.expected_loc_kind
    )
    data.requires_external_confirm = item.expected_loc_kind == "外单位"
    data.fixed_asset_no = item.part.fixed_asset_no if item.part else None
    if item.discrepancy is not None:
        data.discrepancy = StocktakeDiscrepancyOut.model_validate(item.discrepancy)
    return data


def _stocktake_out(st) -> StocktakeOut:
    return StocktakeOut(
        id=st.id,
        scope_kind=st.scope_kind,
        scope_value=st.scope_value,
        initiator_id=st.initiator_id,
        initiated_at=st.initiated_at,
        snapshot_at=st.snapshot_at,
        status=st.status,
        summary=stocktake_service.summarize(st),
        items=[_item_out(i) for i in st.items],
    )


@router.post("", response_model=StocktakeOut)
def create_stocktake(
    body: StocktakeCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    operator_id = current_user.id
    require_role(current_user, enums.STOCKTAKE_ROLES)
    try:
        st = stocktake_service.create_stocktake(
            db,
            initiator_id=operator_id,
            scope_kind=body.scope_kind,
            scope_value=body.scope_value,
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    return _stocktake_out(st)


@router.get("", response_model=list[StocktakeListOut])
def list_stocktakes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return stocktake_service.list_stocktakes(db)


@router.get("/{stocktake_id}", response_model=StocktakeOut)
def get_stocktake(
    stocktake_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        st = stocktake_service.get_stocktake(db, stocktake_id)
    except BusinessError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    return _stocktake_out(st)


@router.get("/{stocktake_id}/items", response_model=list[StocktakeItemOut])
def list_items(
    stocktake_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        st = stocktake_service.get_stocktake(db, stocktake_id)
    except BusinessError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    return [_item_out(i) for i in st.items]


@router.post("/{stocktake_id}/check", response_model=StocktakeItemOut)
def check(
    stocktake_id: int,
    body: StocktakeCheckIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.STOCKTAKE_ROLES)
    operator_id = current_user.id
    try:
        item = stocktake_service.check_item(
            db,
            stocktake_id=stocktake_id,
            operator_id=operator_id,
            **body.model_dump(),
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    return _item_out(item)


@router.post("/{stocktake_id}/confirm-external", response_model=StocktakeItemOut)
def confirm_external(
    stocktake_id: int,
    body: StocktakeConfirmExternalIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.STOCKTAKE_ROLES)
    operator_id = current_user.id
    try:
        item = stocktake_service.confirm_external(
            db,
            stocktake_id=stocktake_id,
            operator_id=operator_id,
            **body.model_dump(),
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    return _item_out(item)


@router.get("/{stocktake_id}/discrepancies", response_model=list[StocktakeDiscrepancyOut])
def discrepancies(
    stocktake_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        rows = stocktake_service.list_discrepancies(db, stocktake_id)
    except BusinessError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    return rows


@router.post("/{stocktake_id}/complete", response_model=StocktakeOut)
def complete(
    stocktake_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    operator_id = current_user.id
    require_role(current_user, enums.STOCKTAKE_ROLES)
    try:
        st = stocktake_service.complete_stocktake(
            db, stocktake_id=stocktake_id, operator_id=operator_id
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    return _stocktake_out(st)
