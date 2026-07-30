from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enums
from ..models import MovementLog, Part


class BusinessError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


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
