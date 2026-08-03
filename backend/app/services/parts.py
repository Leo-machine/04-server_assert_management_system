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
    source_type: str,
    allocatable_flag: str,
    remark: str,
    serial_no: str,
    purchase_amount: Decimal,
    storage_location_id: Optional[int] = None,
    server_id: Optional[int] = None,
    responsible_group: Optional[str] = None,
    contract_no: Optional[str] = None,
    purchase_date: Optional[date] = None,
    supplier: Optional[str] = None,
    project: Optional[str] = None,
    owner_unit: Optional[str] = None,
    warranty_expiry: Optional[date] = None,
    sensitivity: Optional[str] = None,
) -> Part:
    # ---- 通用校验 ----
    if not fixed_asset_no.strip():
        raise BusinessError("固定资产编号必填")
    if not serial_no.strip():
        raise BusinessError("设备序列（SN）号必填")
    if source_type not in enums.SOURCE_TYPES:
        raise BusinessError(f"非法 source_type: {source_type}")
    if allocatable_flag not in enums.ALLOCATABLE_FLAGS:
        raise BusinessError(
            f"非法 allocatable_flag: {allocatable_flag}，"
            f"允许：{' / '.join(enums.ALLOCATABLE_FLAGS)}"
        )
    if not remark.strip():
        raise BusinessError("备注必填")

    model = db.get(PartModel, model_id)
    if model is None:
        raise BusinessError("型号不存在")
    if model.category == "服务器":
        raise BusinessError("服务器整机请走「服务器管理」建档，不走配件入库")
    # 入库前确认型号规格仍符合类型定义（保证数据可用）
    from ..category_specs import SpecValidationError, validate_and_normalize_spec

    try:
        validate_and_normalize_spec(model.category, model.spec)
    except SpecValidationError as e:
        raise BusinessError(f"所选型号规格不完整，请先在型号管理中补全：{e.message}") from e

    exists = db.scalars(
        select(Part).where(Part.fixed_asset_no == fixed_asset_no)
    ).first()
    if exists:
        raise BusinessError(f"固定资产编号已存在: {fixed_asset_no}")

    # ---- 按来源分流 ----
    if source_type == enums.SOURCE_ORIGINAL:
        # 服务器原装：合同/产权/供应商/部门由服务器档案带出；配件直接在装（在用）
        if server_id is None:
            raise BusinessError("服务器原装入库必须选择关联服务器")
        server = db.get(Server, server_id)
        if server is None:
            raise BusinessError("关联服务器不存在")
        missing = []
        if not (server.supplier or "").strip():
            missing.append("供应商")
        if not (server.contract_no or "").strip():
            missing.append("合同号")
        if not (server.responsible_group or "").strip():
            missing.append("运维部门")
        if missing:
            raise BusinessError(
                f"服务器「{server.asset_no}」档案缺少：{'、'.join(missing)}，"
                f"请先在服务器管理中补全后再入库"
            )
        supplier_v = server.supplier
        contract_v = server.contract_no
        project_v = server.project
        owner_v = (server.owner_unit or "").strip() or enums.HOME_OWNER_UNIT
        group_v = server.responsible_group
        warranty_v = server.warranty_expiry
        purchase_date_v = server.arrival_date
        status_to = enums.STATUS_IN_USE
        loc_kind = enums.LOC_SERVER
        loc_id = server.id
    else:
        # 独立合同采购 / 框招正偏移：全字段手填，入在库
        if storage_location_id is None:
            raise BusinessError("必须选择存放位置")
        loc = db.get(StorageLocation, storage_location_id)
        if loc is None:
            raise BusinessError("库位不存在")
        allowed = loc.allowed_categories or []
        if allowed and model.category not in allowed:
            raise BusinessError(
                f"库位「{loc.warehouse}/{loc.slot}」仅允许："
                f"{' / '.join(allowed)}，当前型号类型为「{model.category}」"
            )
        missing = []
        for label, val in (
            ("运维部门", responsible_group),
            ("供应商", supplier),
            ("合同号", contract_no),
            ("所属项目", project),
            ("产权单位", owner_unit),
            ("到货验收日期", purchase_date),
            ("维保到位时间", warranty_expiry),
        ):
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(label)
        if missing:
            raise BusinessError(f"以下字段必填：{'、'.join(missing)}")
        if responsible_group not in enums.RESPONSIBLE_GROUPS:
            raise BusinessError(f"非法 responsible_group: {responsible_group}")
        supplier_v = supplier.strip()
        contract_v = contract_no.strip()
        project_v = project.strip()
        owner_v = owner_unit.strip()
        group_v = responsible_group
        warranty_v = warranty_expiry
        purchase_date_v = purchase_date
        status_to = enums.STATUS_IN_STOCK
        loc_kind = enums.LOC_STORAGE
        loc_id = storage_location_id

    part = Part(
        model_id=model_id,
        fixed_asset_no=fixed_asset_no,
        serial_no=serial_no,
        source_type=source_type,
        contract_no=contract_v,
        purchase_amount=purchase_amount,
        purchase_date=purchase_date_v,
        responsible_group=group_v,
        sensitivity=sensitivity or "无",
        supplier=supplier_v,
        project=project_v,
        owner_unit=owner_v,
        warranty_expiry=warranty_v,
        allocatable_flag=allocatable_flag,
        current_status=status_to,
        current_loc_kind=loc_kind,
        current_loc_id=loc_id,
    )
    db.add(part)
    db.flush()

    movement = insert_movement(
        db,
        part_id=part.id,
        event_type=enums.EVENT_INBOUND,
        status_from=None,
        status_to=status_to,
        operator_id=operator_id,
        loc_from_kind=enums.LOC_NONE,
        loc_from_id=None,
        loc_to_kind=loc_kind,
        loc_to_id=loc_id,
        remark=remark,
    )
    apply_projection_from_movement(part, movement)
    if source_type == enums.SOURCE_ORIGINAL:
        db.add(PartServerLink(part_id=part.id, server_id=server_id, slot=None))
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
