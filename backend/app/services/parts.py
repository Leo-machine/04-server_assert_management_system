from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enums
from ..models import (
    Part,
    PartModel,
    PartServerLink,
    Server,
    StorageLocation,
)
from sqlalchemy.exc import IntegrityError

from .movement import (
    BusinessError,
    apply_projection_from_movement,
    handle_integrity_error,
    insert_movement,
    require_status,
)


def inbound(
    db: Session,
    *,
    operator_id: int,
    model_id: int,
    fixed_asset_no: str,
    storage_location_id: int,
    source_type: str,
    responsible_group: str,
    serial_no: str,
    contract_no: str,
    purchase_amount: Decimal,
    purchase_date: date,
    sensitivity: str,
    supplier: str,
    project: str,
    owner_unit: str,
    warranty_expiry: date,
    allocatable_flag: str,
    remark: str,
) -> Part:
    # ---- 全部字段非空校验 ----
    if not fixed_asset_no.strip():
        raise BusinessError("固定资产编号必填")
    if not serial_no.strip():
        raise BusinessError("厂商序列号 SN 必填")
    if source_type not in enums.SOURCE_TYPES:
        raise BusinessError(f"非法 source_type: {source_type}")
    if responsible_group not in enums.RESPONSIBLE_GROUPS:
        raise BusinessError(f"非法 responsible_group: {responsible_group}")
    if not supplier.strip():
        raise BusinessError("供应商必填")
    if not contract_no.strip():
        raise BusinessError("合同号必填")
    if not project.strip():
        raise BusinessError("所属项目必填")
    owner = owner_unit.strip()
    if not owner:
        raise BusinessError("产权单位必填")
    if not remark.strip():
        raise BusinessError("备注必填")
    if sensitivity not in enums.SENSITIVITY_VALUES:
        raise BusinessError(
            f"非法 sensitivity: {sensitivity}，允许：{' / '.join(enums.SENSITIVITY_VALUES)}"
        )

    flag = allocatable_flag
    if flag not in enums.ALLOCATABLE_FLAGS:
        raise BusinessError(
            f"非法 allocatable_flag: {flag}，允许：{' / '.join(enums.ALLOCATABLE_FLAGS)}"
        )

    model = db.get(PartModel, model_id)
    if model is None:
        raise BusinessError("型号不存在")
    # 入库前确认型号规格仍符合类型定义（保证数据可用）
    from ..category_specs import SpecValidationError, validate_and_normalize_spec

    try:
        validate_and_normalize_spec(model.category, model.spec)
    except SpecValidationError as e:
        raise BusinessError(f"所选型号规格不完整，请先在型号管理中补全：{e.message}") from e
    loc = db.get(StorageLocation, storage_location_id)
    if loc is None:
        raise BusinessError("库位不存在")
    allowed = loc.allowed_categories or []
    if allowed and model.category not in allowed:
        raise BusinessError(
            f"库位「{loc.warehouse}/{loc.slot}」仅允许："
            f"{' / '.join(allowed)}，当前型号类型为「{model.category}」"
        )
    exists = db.scalars(
        select(Part).where(Part.fixed_asset_no == fixed_asset_no)
    ).first()
    if exists:
        raise BusinessError(f"固定资产编号已存在: {fixed_asset_no}")

    part = Part(
        model_id=model_id,
        fixed_asset_no=fixed_asset_no,
        serial_no=serial_no,
        source_type=source_type,
        contract_no=contract_no,
        purchase_amount=purchase_amount,
        purchase_date=purchase_date,
        responsible_group=responsible_group,
        sensitivity=sensitivity,
        supplier=supplier,
        project=project,
        owner_unit=owner,
        warranty_expiry=warranty_expiry,
        allocatable_flag=flag,
        current_status=enums.STATUS_IN_STOCK,
        current_loc_kind=enums.LOC_STORAGE,
        current_loc_id=storage_location_id,
    )
    db.add(part)
    db.flush()

    movement = insert_movement(
        db,
        part_id=part.id,
        event_type=enums.EVENT_INBOUND,
        status_from=None,
        status_to=enums.STATUS_IN_STOCK,
        operator_id=operator_id,
        loc_from_kind=enums.LOC_NONE,
        loc_from_id=None,
        loc_to_kind=enums.LOC_STORAGE,
        loc_to_id=storage_location_id,
        remark=remark,
    )
    apply_projection_from_movement(part, movement)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise handle_integrity_error(e, "固定资产编号可能已存在") from e
    db.refresh(part)
    return part


def install(
    db: Session,
    *,
    part_id: int,
    operator_id: int,
    server_id: int,
    slot: Optional[str] = None,
    remark: Optional[str] = None,
) -> Part:
    part = db.get(Part, part_id)
    if part is None:
        raise BusinessError("配件不存在")
    require_status(part, {enums.STATUS_IN_STOCK}, "装机")

    server = db.get(Server, server_id)
    if server is None:
        raise BusinessError("服务器不存在")
    if part.server_link is not None:
        raise BusinessError("配件已有安装关系")

    from_kind = part.current_loc_kind
    from_id = part.current_loc_id

    movement = insert_movement(
        db,
        part_id=part.id,
        event_type=enums.EVENT_INSTALL,
        status_from=part.current_status,
        status_to=enums.STATUS_IN_USE,
        operator_id=operator_id,
        loc_from_kind=from_kind,
        loc_from_id=from_id,
        loc_to_kind=enums.LOC_SERVER,
        loc_to_id=server_id,
        remark=remark,
    )
    apply_projection_from_movement(part, movement)
    db.add(
        PartServerLink(part_id=part.id, server_id=server_id, slot=slot)
    )
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise handle_integrity_error(e, "配件已有安装关系") from e
    db.refresh(part)
    return part


def uninstall(
    db: Session,
    *,
    part_id: int,
    operator_id: int,
    storage_location_id: int,
    damaged: bool = False,
    remark: Optional[str] = None,
) -> Part:
    part = db.get(Part, part_id)
    if part is None:
        raise BusinessError("配件不存在")
    require_status(part, {enums.STATUS_IN_USE}, "拆下")

    link = part.server_link
    if link is None:
        raise BusinessError("配件无当前安装关系，无法拆下")

    server = db.get(Server, link.server_id)
    if server is None:
        raise BusinessError("服务器不存在")
    if server.run_status == enums.RUN_LIVE:
        raise BusinessError("投运锁拆：服务器处于「投运」，禁止拆下配件")

    loc = db.get(StorageLocation, storage_location_id)
    if loc is None:
        raise BusinessError("目标库位不存在")

    # damaged=True 即坏件拆下：在用 → 损坏（好件则回到在库）
    status_to = enums.STATUS_DAMAGED if damaged else enums.STATUS_IN_STOCK

    movement = insert_movement(
        db,
        part_id=part.id,
        event_type=enums.EVENT_UNINSTALL,
        status_from=part.current_status,
        status_to=status_to,
        operator_id=operator_id,
        loc_from_kind=enums.LOC_SERVER,
        loc_from_id=server.id,
        loc_to_kind=enums.LOC_STORAGE,
        loc_to_id=storage_location_id,
        remark=remark,
    )
    apply_projection_from_movement(part, movement)
    db.delete(link)
    db.commit()
    db.refresh(part)
    return part


def report_damage(
    db: Session,
    *,
    part_id: int,
    operator_id: int,
    remark: str,
) -> Part:
    """库内发现坏件：在库 → 损坏。事件沿用设计文档「坏件拆下」（拆下），位置不变。"""
    part = db.get(Part, part_id)
    if part is None:
        raise BusinessError("配件不存在")
    require_status(part, {enums.STATUS_IN_STOCK}, "报损")
    if not (remark or "").strip():
        raise BusinessError("报损必须填写 remark 说明损坏情况")

    movement = insert_movement(
        db,
        part_id=part.id,
        event_type=enums.EVENT_UNINSTALL,
        status_from=part.current_status,
        status_to=enums.STATUS_DAMAGED,
        operator_id=operator_id,
        loc_from_kind=part.current_loc_kind,
        loc_from_id=part.current_loc_id,
        loc_to_kind=part.current_loc_kind,
        loc_to_id=part.current_loc_id,
        remark=remark.strip(),
    )
    apply_projection_from_movement(part, movement)
    db.commit()
    db.refresh(part)
    return part


def return_from_loan(
    db: Session,
    *,
    part_id: int,
    operator_id: int,
    storage_location_id: int,
    remark: Optional[str] = None,
) -> Part:
    part = db.get(Part, part_id)
    if part is None:
        raise BusinessError("配件不存在")
    require_status(part, {enums.STATUS_LOANED}, "归还")

    loc = db.get(StorageLocation, storage_location_id)
    if loc is None:
        raise BusinessError("目标库位不存在")

    from_kind = part.current_loc_kind
    from_id = part.current_loc_id

    movement = insert_movement(
        db,
        part_id=part.id,
        event_type=enums.EVENT_RETURN,
        status_from=part.current_status,
        status_to=enums.STATUS_IN_STOCK,
        operator_id=operator_id,
        loc_from_kind=from_kind,
        loc_from_id=from_id,
        loc_to_kind=enums.LOC_STORAGE,
        loc_to_id=storage_location_id,
        remark=remark,
    )
    apply_projection_from_movement(part, movement)
    db.commit()
    db.refresh(part)
    return part


def set_server_run_status(db: Session, server_id: int, run_status: str) -> Server:
    if run_status not in (enums.RUN_NOT_LIVE, enums.RUN_LIVE):
        raise BusinessError("demo 仅允许在「未投运」与「投运」之间切换，不可设为退役")
    server = db.get(Server, server_id)
    if server is None:
        raise BusinessError("服务器不存在")
    if server.run_status == enums.RUN_RETIRED:
        raise BusinessError("退役服务器不可切换运行状态")
    server.run_status = run_status
    db.commit()
    db.refresh(server)
    return server


def update_public_fields(
    db: Session,
    *,
    part_id: int,
    supplier: Optional[str] = None,
    project: Optional[str] = None,
    owner_unit: Optional[str] = None,
    warranty_expiry: Optional[date] = None,
    allocatable_flag: Optional[str] = None,
    clear_warranty: bool = False,
) -> Part:
    """仅更新七类公共字段；不写履历、不改状态/位置。"""
    part = db.get(Part, part_id)
    if part is None:
        raise BusinessError("配件不存在")
    if supplier is not None:
        part.supplier = supplier or None
    if project is not None:
        part.project = project or None
    if owner_unit is not None:
        ou = owner_unit.strip()
        if not ou:
            raise BusinessError("产权单位不能为空")
        part.owner_unit = ou
    if clear_warranty:
        part.warranty_expiry = None
    elif warranty_expiry is not None:
        part.warranty_expiry = warranty_expiry
    if allocatable_flag is not None:
        if allocatable_flag not in enums.ALLOCATABLE_FLAGS:
            raise BusinessError(
                f"非法 allocatable_flag: {allocatable_flag}，"
                f"允许：{' / '.join(enums.ALLOCATABLE_FLAGS)}"
            )
        if part.current_status != enums.STATUS_IN_STOCK:
            raise BusinessError(
                f"仅「在库」配件可调整可调配标记，当前状态：{part.current_status}"
            )
        part.allocatable_flag = allocatable_flag
    db.commit()
    db.refresh(part)
    return part
