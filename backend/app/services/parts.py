from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enums
from ..models import (
    Approval,
    MovementLog,
    Part,
    PartModel,
    PartServerLink,
    Server,
    ServerMovementLog,
    StorageLocation,
    Supplier,
)
from sqlalchemy.exc import IntegrityError

from . import approvals as approvals_service
from .movement import (
    BusinessError,
    apply_projection_from_movement,
    handle_integrity_error,
    insert_movement,
    require_status,
)
from ..category_specs import CATEGORY_ASSET_PREFIX, validate_category


def _require_location_category(loc: StorageLocation, part_or_model: Part | PartModel) -> None:
    """校验库位的品类限制，供入库、拆下和归还共用。"""
    model = part_or_model.model if isinstance(part_or_model, Part) else part_or_model
    allowed = loc.allowed_categories or []
    if allowed and model.category not in allowed:
        raise BusinessError(
            f"库位「{loc.warehouse}/{loc.slot}」仅允许："
            f"{' / '.join(allowed)}，当前型号类型为「{model.category}」"
        )


def generate_next_fixed_asset_no(db: Session, category: str) -> str:
    """生成下一条固定资产编号：PREFIX-YYYYMMDD-NNN（当天该品类最大序号+1）。

    仅用于前端预填建议值；实际入库时以 DB UNIQUE 约束为最终保障。
    """
    prefix = CATEGORY_ASSET_PREFIX.get(category)
    if prefix is None:
        validate_category(category)
        raise BusinessError(f"未定义固定资产编号前缀: {category}")

    today_str = date.today().strftime("%Y%m%d")
    pattern = f"{prefix}-{today_str}-%"

    existing = db.scalars(
        select(Part.fixed_asset_no).where(Part.fixed_asset_no.like(pattern))
    ).all()

    max_seq = 0
    for no in existing:
        try:
            seq = int(no.rsplit("-", 1)[-1])
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue

    return f"{prefix}-{today_str}-{max_seq + 1:03d}"


def inbound(
    db: Session,
    *,
    operator_id: int,
    model_id: int,
    fixed_asset_no: str = "",
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
    commit: bool = True,
) -> Part:
    # ---- 通用校验 ----
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

    # 固定资产编号：空则按品类自动生成，填了则使用用户输入值
    auto_generated = not fixed_asset_no.strip()
    original_input = fixed_asset_no

    if auto_generated:
        fixed_asset_no = generate_next_fixed_asset_no(db, model.category)
    else:
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
        _require_location_category(loc, model)
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
        # 非原装：供应商须在名录中（与批量导入一致）
        if supplier_v:
            known = db.scalars(
                select(Supplier).where(Supplier.name == supplier_v)
            ).first()
            if known is None:
                raise BusinessError(f"供应商「{supplier_v}」不在名录中，请先维护")
        contract_v = contract_no.strip()
        project_v = project.strip()
        owner_v = owner_unit.strip()
        group_v = responsible_group
        warranty_v = warranty_expiry
        purchase_date_v = purchase_date
        status_to = enums.STATUS_IN_STOCK
        loc_kind = enums.LOC_STORAGE
        loc_id = storage_location_id

    MAX_RETRIES = 5 if auto_generated else 1
    for attempt in range(MAX_RETRIES):
        try:
            # rollback 后 ORM 对象可能已脱离 Session；每次重试都完整重建
            # 配件、入库履历与原装绑定，确保三者始终同一事务。
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
            if commit:
                db.commit()
                db.refresh(part)
            else:
                db.flush()
            return part
        except IntegrityError as e:
            db.rollback()
            if not auto_generated or attempt >= MAX_RETRIES - 1:
                raise handle_integrity_error(e, "固定资产编号可能已存在") from e
            # 自动生成冲突：递增序号重试
            import time
            time.sleep(0.05 * (attempt + 1))
            fixed_asset_no = generate_next_fixed_asset_no(db, model.category)

    raise BusinessError("固定资产编号自动生成失败，已达最大重试次数，请稍后重试")


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
    approvals_service.assert_no_inflight_approval(db, part_id)
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
    approvals_service.assert_no_inflight_approval(db, part_id)
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
    _require_location_category(loc, part)

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


def delete_part(db: Session, *, part_id: int) -> None:
    """删除误录配件；仅限未发生后续业务流转的在库记录。"""
    part = db.get(Part, part_id)
    if part is None:
        raise BusinessError("配件不存在")
    require_status(part, {enums.STATUS_IN_STOCK}, "删除")
    if part.server_link is not None:
        raise BusinessError("配件存在装机关系，不能删除")
    if db.scalars(
        select(Approval.id).where(Approval.part_id == part_id).limit(1)
    ).first() is not None:
        raise BusinessError("配件已有审批记录，不能删除；请保留审计履历")

    movements = list(
        db.scalars(
            select(MovementLog)
            .where(MovementLog.part_id == part_id)
            .order_by(MovementLog.id)
        ).all()
    )
    if len(movements) != 1 or movements[0].event_type != enums.EVENT_INBOUND:
        raise BusinessError("配件已有业务流转履历，不能删除；仅支持清理未流转的误录数据")

    db.delete(movements[0])
    db.delete(part)
    db.commit()


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
    approvals_service.assert_no_inflight_approval(db, part_id)
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
    approvals_service.assert_no_inflight_approval(db, part_id)
    require_status(part, {enums.STATUS_LOANED}, "归还")

    loc = db.get(StorageLocation, storage_location_id)
    if loc is None:
        raise BusinessError("目标库位不存在")
    _require_location_category(loc, part)

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


def set_server_run_status(
    db: Session, server_id: int, run_status: str,
    *, work_order_no: str = "", operator_id: int = 0,
) -> Server:
    if run_status not in (enums.RUN_NOT_LIVE, enums.RUN_LIVE):
        raise BusinessError("仅允许在「未投运」与「投运」之间切换，不可设为退役")
    if not (work_order_no or "").strip():
        raise BusinessError("必须提供工作票工单号")
    server = db.get(Server, server_id)
    if server is None:
        raise BusinessError("服务器不存在")
    if server.run_status == enums.RUN_RETIRED:
        raise BusinessError("退役服务器不可切换运行状态")

    status_from = server.run_status
    server.run_status = run_status

    movement = ServerMovementLog(
        server_id=server.id,
        event_type="切换运行状态",
        run_status_from=status_from,
        run_status_to=run_status,
        occurred_at=datetime.now(timezone.utc),
        operator_id=operator_id,
        work_order_no=work_order_no.strip(),
    )
    db.add(movement)
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
