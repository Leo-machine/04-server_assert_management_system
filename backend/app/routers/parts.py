from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .. import enums
from ..database import get_db
from ..deps import get_current_user, get_operator_id, require_role
from ..models import User
from ..models import Part
from ..schemas import (
    DamageIn,
    InboundIn,
    InstallIn,
    MovementOut,
    PartOut,
    PartPublicUpdateIn,
    ReplayOut,
    ReturnIn,
    UninstallIn,
)
from ..services.movement import (
    BusinessError,
    batch_is_overdue,
    list_movements,
    replay_projection,
)
from ..services import parts as parts_service
from ..services import parts_batch as parts_batch_service

router = APIRouter(tags=["parts"])


class BatchImportIn(BaseModel):
    content: str  # CSV 文本（UTF-8）


def _csv_response(text: str, filename: str) -> Response:
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _parts_out(db: Session, parts: list[Part]) -> list[PartOut]:
    """批量构造 PartOut，一次性计算所有配件的超期状态，避免 N+1 查询。"""
    overdue_ids = batch_is_overdue(db, [p for p in parts if p.current_status == enums.STATUS_LOANED])
    results = []
    for p in parts:
        data = PartOut.model_validate(p)
        data.is_overdue = p.current_status == enums.STATUS_LOANED and p.id in overdue_ids
        results.append(data)
    return results


def _part_out(db: Session, part: Part) -> PartOut:
    return _parts_out(db, [part])[0]


@router.get("/parts", response_model=list[PartOut])
def list_parts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.VIEW_PARTS_ROLES)
    parts = list(
        db.scalars(
            select(Part).options(joinedload(Part.model)).order_by(Part.id)
        ).unique().all()
    )
    return _parts_out(db, parts)


@router.get("/parts/export.csv")
def export_parts(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.INVENTORY_ROLES)
    return _csv_response(
        parts_batch_service.export_parts_csv(db, category=category),
        "parts_export.csv",
    )


@router.get("/parts/next-asset-no")
def next_asset_no(
    category: str = Query(..., description="配件类型，如：内存"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回指定类型当天的下一个建议固定资产编号（仅供前端预填）。"""
    require_role(current_user, enums.INBOUND_ROLES)
    try:
        no = parts_service.generate_next_fixed_asset_no(db, category)
        return {"fixed_asset_no": no, "category": category}
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.get("/parts/import-template.csv")
def parts_import_template(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.INBOUND_ROLES)
    return _csv_response(
        parts_batch_service.import_template_csv(db, category=category),
        "parts_import_template.csv",
    )


@router.post("/parts/batch-import")
def batch_import_parts(
    body: BatchImportIn,
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
    current_user: User = Depends(get_current_user),
):
    """两段式批量入库：dry_run=true 校验预览；dry_run=false 整批通过才入库。"""
    require_role(current_user, enums.INBOUND_ROLES)
    try:
        return parts_batch_service.batch_import_parts(
            db, body.content, operator_id=operator_id, dry_run=dry_run
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.get("/parts/{part_id}", response_model=PartOut)
def get_part(
    part_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.VIEW_PARTS_ROLES)
    part = db.scalars(
        select(Part).options(joinedload(Part.model)).where(Part.id == part_id)
    ).unique().first()
    if part is None:
        raise HTTPException(status_code=404, detail="配件不存在")
    return _part_out(db, part)


@router.get("/parts/{part_id}/movements", response_model=list[MovementOut])
def get_movements(
    part_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.VIEW_PARTS_ROLES)
    if db.get(Part, part_id) is None:
        raise HTTPException(status_code=404, detail="配件不存在")
    return list_movements(db, part_id)


@router.get("/parts/{part_id}/projected-from-log", response_model=ReplayOut)
def projected_from_log(
    part_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.VIEW_PARTS_ROLES)
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
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.INBOUND_ROLES)
    try:
        part = parts_service.inbound(db, operator_id=operator_id, **body.model_dump())
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    part = db.scalars(
        select(Part).options(joinedload(Part.model)).where(Part.id == part.id)
    ).unique().one()
    return _part_out(db, part)


@router.patch("/parts/{part_id}", response_model=PartOut)
def patch_part_public(
    part_id: int,
    body: PartPublicUpdateIn,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
    current_user: User = Depends(get_current_user),
):
    """更新实物公共字段（供应商/项目/产权/维保/可调配标记），不写履历。"""
    require_role(current_user, enums.LOAN_RETURN_ROLES)
    try:
        part = parts_service.update_public_fields(
            db, part_id=part_id, **body.model_dump()
        )
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
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.INSTALL_UNINSTALL_ROLES)
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
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.INSTALL_UNINSTALL_ROLES)
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


@router.delete("/parts/{part_id}")
def delete_part(
    part_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除误录资产：仅领导可操作，已有业务履历的数据禁止删除。"""
    require_role(current_user, (enums.ROLE_LEADER,))
    try:
        parts_service.delete_part(db, part_id=part_id)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    return {"ok": True}


@router.post("/parts/{part_id}/damage", response_model=PartOut)
def damage(
    part_id: int,
    body: DamageIn,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.LOAN_RETURN_ROLES)
    try:
        part = parts_service.report_damage(
            db,
            part_id=part_id,
            operator_id=operator_id,
            remark=body.remark,
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
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.LOAN_RETURN_ROLES)
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
