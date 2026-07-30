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
from .movement import (
    BusinessError,
    apply_projection_from_movement,
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
    serial_no: Optional[str] = None,
    contract_no: Optional[str] = None,
    purchase_amount: Optional[Decimal] = None,
    purchase_date: Optional[date] = None,
    sensitivity: Optional[str] = None,
    remark: Optional[str] = None,
) -> Part:
    if source_type not in enums.SOURCE_TYPES:
        raise BusinessError(f"非法 source_type: {source_type}")
    if responsible_group not in enums.RESPONSIBLE_GROUPS:
        raise BusinessError(f"非法 responsible_group: {responsible_group}")

    model = db.get(PartModel, model_id)
    if model is None:
        raise BusinessError("型号不存在")
    loc = db.get(StorageLocation, storage_location_id)
    if loc is None:
        raise BusinessError("库位不存在")
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
    db.commit()
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
    db.commit()
    db.refresh(part)
    return part


def uninstall(
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

    movement = insert_movement(
        db,
        part_id=part.id,
        event_type=enums.EVENT_UNINSTALL,
        status_from=part.current_status,
        status_to=enums.STATUS_IN_STOCK,
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
