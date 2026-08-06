"""用户账号状态字段迁移：幂等 ALTER ADD COLUMN + 存量用户置「正常」。"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_USER_NEW_COLS = [
    ("status", "VARCHAR(20) NOT NULL DEFAULT '正常'"),
    ("applied_role", "VARCHAR(20)"),
    ("apply_reason", "VARCHAR(200)"),
    ("reject_reason", "VARCHAR(200)"),
    ("reviewed_by_id", "INTEGER"),
    ("reviewed_at", "DATETIME"),
]


def migrate_user_status(db: Session) -> dict[str, Any]:
    rows = db.execute(text("PRAGMA table_info(user)")).all()
    cols = {r[1] for r in rows}
    added: list[str] = []
    for name, typ in _USER_NEW_COLS:
        if name in cols:
            continue
        db.execute(text(f'ALTER TABLE user ADD COLUMN {name} {typ}'))
        added.append(name)
    db.commit()
    if added:
        logger.info("user 状态字段迁移: added=%s", added)
    return {"added": added}
