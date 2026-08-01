from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Part, StorageLocation
from .movement import BusinessError


def list_locations(db: Session, category: Optional[str] = None) -> list[dict]:
    """列出库位；可选按配件类型过滤 allowed_categories。返回带 part_count 的字典列表。"""
    rows = list(db.scalars(select(StorageLocation).order_by(StorageLocation.id)).all())

    # 统计每个库位的配件数量
    part_counts: dict[int, int] = {}
    if rows:
        counts = (
            db.execute(
                select(
                    Part.current_loc_id,
                    Part.current_status,
                ).where(
                    Part.current_loc_kind == "库位",
                    Part.current_loc_id.in_([r.id for r in rows]),
                )
            )
            .all()
        )
        for loc_id, _status in counts:
            part_counts[loc_id] = part_counts.get(loc_id, 0) + 1

    result = []
    for r in rows:
        cats = r.allowed_categories or []
        # 按类别过滤
        if category and cats and category not in cats:
            continue
        result.append({
            "id": r.id,
            "warehouse": r.warehouse,
            "slot": r.slot,
            "location_type": r.location_type,
            "allowed_categories": r.allowed_categories,
            "part_count": part_counts.get(r.id, 0),
        })
    return result


def location_distribution(db: Session) -> list[dict]:
    """每个库位的配件状态分布。"""
    rows = list(db.scalars(select(StorageLocation).order_by(StorageLocation.id)).all())
    if not rows:
        return []

    loc_ids = [r.id for r in rows]
    counts = (
        db.execute(
            select(
                Part.current_loc_id,
                Part.current_status,
            ).where(
                Part.current_loc_kind == "库位",
                Part.current_loc_id.in_(loc_ids),
            )
        )
        .all()
    )

    by_loc: dict[int, dict] = {}
    for loc_id, status in counts:
        if loc_id not in by_loc:
            by_loc[loc_id] = {"part_count": 0, "parts_by_status": {}}
        by_loc[loc_id]["part_count"] += 1
        by_loc[loc_id]["parts_by_status"][status] = (
            by_loc[loc_id]["parts_by_status"].get(status, 0) + 1
        )

    result = []
    for r in rows:
        stats = by_loc.get(r.id, {"part_count": 0, "parts_by_status": {}})
        result.append({
            "id": r.id,
            "warehouse": r.warehouse,
            "slot": r.slot,
            "location_type": r.location_type,
            "allowed_categories": r.allowed_categories,
            "part_count": stats["part_count"],
            "parts_by_status": stats["parts_by_status"],
        })
    return result


def create_location(
    db: Session,
    *,
    warehouse: str,
    slot: str,
    location_type: Optional[str] = None,
    allowed_categories: Optional[list] = None,
) -> StorageLocation:
    wh = warehouse.strip()
    sl = slot.strip()
    if not wh:
        raise BusinessError("区域名称必填")
    if not sl:
        raise BusinessError("位置必填")
    if location_type and location_type not in ("库房货架", "机房备件柜", "数据中心机柜", "其他"):
        raise BusinessError(f"非法位置类型：{location_type}")
    dup = db.scalars(
        select(StorageLocation).where(
            StorageLocation.warehouse == wh,
            StorageLocation.slot == sl,
        )
    ).first()
    if dup is not None:
        raise BusinessError(f"存放位置「{wh}/{sl}」已存在")
    row = StorageLocation(
        warehouse=wh,
        slot=sl,
        location_type=location_type or None,
        allowed_categories=allowed_categories or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_location(
    db: Session,
    location_id: int,
    *,
    warehouse: Optional[str] = None,
    slot: Optional[str] = None,
    location_type: Optional[str] = None,
    allowed_categories: Optional[list] = None,
) -> StorageLocation:
    row = db.get(StorageLocation, location_id)
    if row is None:
        raise BusinessError("存放位置不存在")
    if warehouse is not None:
        wh = warehouse.strip()
        if not wh:
            raise BusinessError("区域名称必填")
        row.warehouse = wh
    if slot is not None:
        sl = slot.strip()
        if not sl:
            raise BusinessError("位置必填")
        row.slot = sl
    if location_type is not None:
        if location_type not in ("库房货架", "机房备件柜", "数据中心机柜", "其他"):
            raise BusinessError(f"非法位置类型：{location_type}")
        row.location_type = location_type
    if allowed_categories is not None:
        row.allowed_categories = allowed_categories if allowed_categories else None

    dup = db.scalars(
        select(StorageLocation).where(
            StorageLocation.warehouse == row.warehouse,
            StorageLocation.slot == row.slot,
            StorageLocation.id != location_id,
        )
    ).first()
    if dup is not None:
        raise BusinessError(f"存放位置「{row.warehouse}/{row.slot}」已存在")
    db.commit()
    db.refresh(row)
    return row


def delete_location(db: Session, location_id: int) -> None:
    row = db.get(StorageLocation, location_id)
    if row is None:
        raise BusinessError("存放位置不存在")
    in_use = db.scalars(
        select(Part.id).where(
            Part.current_loc_kind == "库位",
            Part.current_loc_id == location_id,
        ).limit(1)
    ).first()
    if in_use is not None:
        raise BusinessError("该位置仍有配件存放，请先转移后再删除")
    db.delete(row)
    db.commit()
