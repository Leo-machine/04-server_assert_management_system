"""第一波表结构迁移：approval 重建放宽约束 + movement_log 加列。幂等。

- approval：expected_return_date / dest_org_id 放宽为可空，
  新增 reason_code / attachment_ref。SQLite 无法改列约束，用
  建新表 → 拷贝 → 删旧表 → 改名 的标准流程。
- movement_log：ALTER TABLE ADD COLUMN reason_code / event_group_id。
- 新装环境由 create_all 直接建出新结构，本脚本检测到新结构即跳过。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_APPROVAL_NEW_DDL = """
CREATE TABLE approval_new (
    id INTEGER NOT NULL PRIMARY KEY,
    part_id INTEGER NOT NULL REFERENCES part (id),
    action_type VARCHAR(50) NOT NULL,
    applicant_id INTEGER NOT NULL REFERENCES "user" (id),
    applied_at DATETIME NOT NULL,
    overall_status VARCHAR(50) NOT NULL,
    current_level INTEGER NOT NULL,
    expected_return_date DATE,
    dest_org_id INTEGER REFERENCES external_org (id),
    reason_code VARCHAR(50),
    attachment_ref VARCHAR(200),
    remark TEXT
)
"""

_APPROVAL_COPY_COLS = (
    "id, part_id, action_type, applicant_id, applied_at, overall_status, "
    "current_level, expected_return_date, dest_org_id, remark"
)


def _table_columns(db: Session, table: str) -> dict[str, dict[str, Any]]:
    rows = db.execute(text(f"PRAGMA table_info({table})")).all()
    # cid, name, type, notnull, dflt_value, pk
    return {
        r[1]: {"notnull": bool(r[3]), "pk": bool(r[5])}
        for r in rows
    }


def _migrate_movement_log(db: Session) -> list[str]:
    cols = _table_columns(db, "movement_log")
    added: list[str] = []
    if "reason_code" not in cols:
        db.execute(
            text("ALTER TABLE movement_log ADD COLUMN reason_code VARCHAR(50)")
        )
        added.append("reason_code")
    if "event_group_id" not in cols:
        db.execute(
            text("ALTER TABLE movement_log ADD COLUMN event_group_id VARCHAR(36)")
        )
        added.append("event_group_id")
    return added


def _migrate_approval(db: Session) -> bool:
    """返回是否执行了重建。"""
    cols = _table_columns(db, "approval")
    already_new = (
        "reason_code" in cols
        and "attachment_ref" in cols
        and not cols.get("expected_return_date", {}).get("notnull", False)
        and not cols.get("dest_org_id", {}).get("notnull", False)
    )
    if already_new:
        return False

    db.execute(text(_APPROVAL_NEW_DDL))
    db.execute(
        text(
            f"INSERT INTO approval_new ({_APPROVAL_COPY_COLS}) "
            f"SELECT {_APPROVAL_COPY_COLS} FROM approval"
        )
    )
    db.execute(text("DROP TABLE approval"))
    db.execute(text("ALTER TABLE approval_new RENAME TO approval"))
    return True


def migrate_wave1(db: Session) -> dict[str, Any]:
    """幂等：检测到新结构即全部跳过。"""
    added = _migrate_movement_log(db)
    rebuilt = _migrate_approval(db)
    db.commit()
    if added or rebuilt:
        logger.info(
            "wave1 迁移完成: movement_log 新增列=%s, approval 重建=%s",
            added,
            rebuilt,
        )
    return {"movement_log_added": added, "approval_rebuilt": rebuilt}
