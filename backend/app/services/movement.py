from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import enums
from ..models import MovementLog, Part


class BusinessError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ConflictError(BusinessError):
    """并发冲突导致的业务错误（如重复固定资产编号、重复安装关系）。"""
    pass


def handle_integrity_error(e: IntegrityError, fallback: str = "数据冲突，请重试") -> BusinessError:
    """将 IntegrityError 转为友好的 BusinessError / ConflictError。"""
    msg = str(e.orig) if e.orig else str(e)
    if "UNIQUE" in msg.upper():
        if "fixed_asset_no" in msg:
            return ConflictError("固定资产编号已存在（并发冲突）")
        if "part_server_link" in msg:
            return ConflictError("配件已有安装关系（并发冲突）")
        return ConflictError(f"唯一性冲突：{fallback}")
    return BusinessError(fallback)


def require_status(part: Part, allowed: set[str], action: str) -> None:
    if part.current_status not in allowed:
        raise BusinessError(
            f"非法起始状态：配件当前为「{part.current_status}」，无法执行「{action}」"
            f"（允许：{'/'.join(sorted(allowed))}）"
        )


def insert_movement(
    db: Session,
    *,
    part_id: int,
    event_type: str,
    status_from: Optional[str],
    status_to: str,
    operator_id: int,
    loc_from_kind: Optional[str] = None,
    loc_from_id: Optional[int] = None,
    loc_to_kind: Optional[str] = None,
    loc_to_id: Optional[int] = None,
    work_order_no: Optional[str] = None,
    approval_id: Optional[int] = None,
    expected_return_date: Optional[date] = None,
    reason_code: Optional[str] = None,
    event_group_id: Optional[str] = None,
    remark: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
) -> MovementLog:
    """履历唯一写入入口：只 INSERT，无 update/delete。"""
    row = MovementLog(
        part_id=part_id,
        event_type=event_type,
        status_from=status_from,
        status_to=status_to,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        operator_id=operator_id,
        loc_from_kind=loc_from_kind,
        loc_from_id=loc_from_id,
        loc_to_kind=loc_to_kind,
        loc_to_id=loc_to_id,
        work_order_no=work_order_no,
        approval_id=approval_id,
        expected_return_date=expected_return_date,
        reason_code=reason_code,
        event_group_id=event_group_id,
        remark=remark,
    )
    db.add(row)
    db.flush()
    return row


def list_movements(db: Session, part_id: int) -> list[MovementLog]:
    stmt = (
        select(MovementLog)
        .where(MovementLog.part_id == part_id)
        .order_by(MovementLog.occurred_at.asc(), MovementLog.id.asc())
    )
    return list(db.scalars(stmt).all())


def latest_movement(db: Session, part_id: int) -> Optional[MovementLog]:
    stmt = (
        select(MovementLog)
        .where(MovementLog.part_id == part_id)
        .order_by(MovementLog.occurred_at.desc(), MovementLog.id.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def replay_projection(db: Session, part_id: int) -> dict:
    """由履历最新一条重放当前状态/位置。"""
    latest = latest_movement(db, part_id)
    if latest is None:
        return {
            "current_status": None,
            "current_loc_kind": None,
            "current_loc_id": None,
        }
    return {
        "current_status": latest.status_to,
        "current_loc_kind": latest.loc_to_kind,
        "current_loc_id": latest.loc_to_id,
    }


def apply_projection_from_movement(part: Part, movement: MovementLog) -> None:
    part.current_status = movement.status_to
    part.current_loc_kind = movement.loc_to_kind
    part.current_loc_id = movement.loc_to_id


def latest_loan_expected_return_date(db: Session, part_id: int) -> Optional[date]:
    """超期判断唯一来源：最新一条借出履历上的 expected_return_date。"""
    stmt = (
        select(MovementLog)
        .where(
            MovementLog.part_id == part_id,
            MovementLog.event_type == enums.EVENT_LOAN,
        )
        .order_by(MovementLog.occurred_at.desc(), MovementLog.id.desc())
        .limit(1)
    )
    row = db.scalars(stmt).first()
    return row.expected_return_date if row else None


def is_overdue(db: Session, part: Part, today: Optional[date] = None) -> bool:
    if part.current_status != enums.STATUS_LOANED:
        return False
    expected = latest_loan_expected_return_date(db, part.id)
    if expected is None:
        return False
    return (today or date.today()) > expected


def batch_is_overdue(db: Session, loaned_parts: list[Part], today: Optional[date] = None) -> set[int]:
    """批量计算借出配件是否超期，一次查询替代 N 次单条查询。"""
    if not loaned_parts:
        return set()
    part_ids = [p.id for p in loaned_parts]

    # 一次拉取所有相关借出履历，在 Python 侧按 part_id 取最新一条
    rows = (
        db.execute(
            select(
                MovementLog.part_id,
                MovementLog.expected_return_date,
                MovementLog.occurred_at,
            )
            .where(
                MovementLog.part_id.in_(part_ids),
                MovementLog.event_type == enums.EVENT_LOAN,
            )
            .order_by(MovementLog.part_id, MovementLog.occurred_at.desc(), MovementLog.id.desc())
        )
        .all()
    )

    # 因已按 (part_id, occurred_at DESC, id DESC) 排序，每组第一条即最新
    seen: set[int] = set()
    latest_by_part: dict[int, date] = {}
    for pid, erd, _occurred in rows:
        if pid in seen:
            continue
        seen.add(pid)
        if erd is not None:
            latest_by_part[pid] = erd

    today_date = today or date.today()
    return {pid for pid, erd in latest_by_part.items() if today_date > erd}
