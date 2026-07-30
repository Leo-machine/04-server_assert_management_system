from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import get_operator_id, require_user
from ..models import Part, PartModel
from ..schemas import (
    InboundIn,
    InstallIn,
    MovementOut,
    PartOut,
    PartModelOut,
    ReplayOut,
    ReturnIn,
    UninstallIn,
)
from ..services.movement import (
    BusinessError,
    is_overdue,
    list_movements,
    replay_projection,
)
from ..services import parts as parts_service

router = APIRouter(tags=["parts"])


def _part_out(db: Session, part: Part) -> PartOut:
    data = PartOut.model_validate(part)
    data.is_overdue = is_overdue(db, part)
    return data


@router.get("/part-models", response_model=list[PartModelOut])
def list_part_models(db: Session = Depends(get_db)):
    return list(db.scalars(select(PartModel).order_by(PartModel.id)).all())


@router.get("/parts", response_model=list[PartOut])
def list_parts(db: Session = Depends(get_db)):
    parts = list(
        db.scalars(
            select(Part).options(joinedload(Part.model)).order_by(Part.id)
        ).unique().all()
    )
    return [_part_out(db, p) for p in parts]


@router.get("/parts/{part_id}", response_model=PartOut)
def get_part(part_id: int, db: Session = Depends(get_db)):
    part = db.scalars(
        select(Part).options(joinedload(Part.model)).where(Part.id == part_id)
    ).unique().first()
    if part is None:
        raise HTTPException(status_code=404, detail="配件不存在")
    return _part_out(db, part)


@router.get("/parts/{part_id}/movements", response_model=list[MovementOut])
def get_movements(part_id: int, db: Session = Depends(get_db)):
    if db.get(Part, part_id) is None:
        raise HTTPException(status_code=404, detail="配件不存在")
    return list_movements(db, part_id)


@router.get("/parts/{part_id}/projected-from-log", response_model=ReplayOut)
def projected_from_log(part_id: int, db: Session = Depends(get_db)):
    part = db.get(Part, part_id)
    if part is None:
        raise HTTPException(status_code=404, detail="配件不存在")
    replayed = replay_projection(db, part_id)
    matches = (
        part.current_status == replayed["current_status"]
        and part.current_loc_kind == replayed["current_loc_kind"]
        and part.current_loc_id == replayed["current_loc_id"]
    )
    return ReplayOut(**replayed, matches_cache=matches)


@router.post("/parts/inbound", response_model=PartOut)
def inbound(
    body: InboundIn,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    require_user(db, operator_id)
    try:
        part = parts_service.inbound(db, operator_id=operator_id, **body.model_dump())
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    part = db.scalars(
        select(Part).options(joinedload(Part.model)).where(Part.id == part.id)
    ).unique().one()
    return _part_out(db, part)


@router.post("/parts/{part_id}/install", response_model=PartOut)
def install(
    part_id: int,
    body: InstallIn,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    require_user(db, operator_id)
    try:
        part = parts_service.install(
            db,
            part_id=part_id,
            operator_id=operator_id,
            **body.model_dump(),
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    part = db.scalars(
        select(Part).options(joinedload(Part.model)).where(Part.id == part.id)
    ).unique().one()
    return _part_out(db, part)


@router.post("/parts/{part_id}/uninstall", response_model=PartOut)
def uninstall(
    part_id: int,
    body: UninstallIn,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    require_user(db, operator_id)
    try:
        part = parts_service.uninstall(
            db,
            part_id=part_id,
            operator_id=operator_id,
            **body.model_dump(),
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    part = db.scalars(
        select(Part).options(joinedload(Part.model)).where(Part.id == part.id)
    ).unique().one()
    return _part_out(db, part)


@router.post("/parts/{part_id}/return", response_model=PartOut)
def return_part(
    part_id: int,
    body: ReturnIn,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    require_user(db, operator_id)
    try:
        part = parts_service.return_from_loan(
            db,
            part_id=part_id,
            operator_id=operator_id,
            **body.model_dump(),
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    part = db.scalars(
        select(Part).options(joinedload(Part.model)).where(Part.id == part.id)
    ).unique().one()
    return _part_out(db, part)
