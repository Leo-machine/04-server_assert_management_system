from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .. import enums
from ..database import get_db
from ..deps import get_operator_id, require_user
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
def list_parts(db: Session = Depends(get_db)):
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
):
    return _csv_response(
        parts_batch_service.export_parts_csv(db, category=category),
        "parts_export.csv",
    )


@router.get("/parts/import-template.csv")
def parts_import_template(
    category: Optional[str] = Query(None),
    operator_id: int = Depends(get_operator_id),
):
    return _csv_response(
        parts_batch_service.import_template_csv(category=category),
        "parts_import_template.csv",
    )


@router.post("/parts/batch-import")
def batch_import_parts(
    body: BatchImportIn,
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    """两段式批量入库：dry_run=true 校验预览；dry_run=false 整批通过才入库。"""
    require_user(db, operator_id)
    try:
        return parts_batch_service.batch_import_parts(
            db, body.content, operator_id=operator_id, dry_run=dry_run
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


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


@router.patch("/parts/{part_id}", response_model=PartOut)
def patch_part_public(
    part_id: int,
    body: PartPublicUpdateIn,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    """更新实物公共字段（供应商/项目/产权/维保/可调配标记），不写履历。"""
    require_user(db, operator_id)
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


@router.post("/parts/{part_id}/damage", response_model=PartOut)
def damage(
    part_id: int,
    body: DamageIn,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    require_user(db, operator_id)
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


# ----- 模板导出 / 批量导入 -----
INBOUND_CSV_HEADER = (
    "固定资产编号,序列号SN,型号ID,来源,运维部门,供应商,合同号,所属项目,"
    "采购金额,采购日期,产权单位,维保到期,可调配标记,敏感标记,备注"
)


@router.get("/parts/inbound/template")
def download_template(category: str):
    from fastapi.responses import PlainTextResponse
    example = (
        f"FA-XXX-001,SN-001,1,独立合同采购,基础组,供应商名,HT-2026-001,演示项目,"
        f"1000.00,2026-01-01,本单位信息中心,2029-01-01,通用可调,无,{category}入库示例"
    )
    return PlainTextResponse(
        f"{INBOUND_CSV_HEADER}\n{example}",
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=inbound-{category}.csv"},
    )


@router.post("/parts/inbound/batch")
def batch_inbound(
    body: dict,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    import csv
    import io

    require_user(db, operator_id)
    csv_text = (body.get("csv_text") or "").strip()
    loc_id = body.get("storage_location_id")
    if not csv_text:
        raise HTTPException(status_code=400, detail="CSV 内容为空")
    if not loc_id:
        raise HTTPException(status_code=400, detail="请选择存放位置")

    reader = csv.DictReader(io.StringIO(csv_text))
    ok_list = []
    errors = []
    for i, row in enumerate(reader, start=1):
        try:
            part = parts_service.inbound(
                db,
                operator_id=operator_id,
                model_id=int(row.get("型号ID", "0")),
                fixed_asset_no=(row.get("固定资产编号") or "").strip(),
                storage_location_id=int(loc_id),
                source_type=row.get("来源") or enums.SOURCE_CONTRACT,
                responsible_group=row.get("运维部门") or "基础组",
                serial_no=(row.get("序列号SN") or "").strip(),
                contract_no=(row.get("合同号") or "").strip(),
                purchase_amount=float(row.get("采购金额") or 0),
                purchase_date=row.get("采购日期") or "2026-01-01",
                sensitivity=row.get("敏感标记") or "无",
                supplier=(row.get("供应商") or "").strip(),
                project=(row.get("所属项目") or row.get("项目") or "批量导入").strip(),
                owner_unit=(row.get("产权单位") or "本单位信息中心").strip(),
                warranty_expiry=row.get("维保到期") or "2029-01-01",
                allocatable_flag=row.get("可调配标记") or "通用可调",
                remark=(row.get("备注") or "").strip(),
            )
            ok_list.append(part.fixed_asset_no)
        except BusinessError as e:
            errors.append(f"第{i}行: {e.message}")
        except Exception as e:
            errors.append(f"第{i}行: {e}")

    return {"ok": len(ok_list), "errors": errors, "items": ok_list}
