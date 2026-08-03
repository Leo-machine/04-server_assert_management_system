"""来源枚举重构迁移：旧值映射到新三值。幂等（只更新旧值行）。"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_MAPPING = {
    "随器采购": "服务器原装",
    "单独合同": "独立合同采购",
    "维保换新": "框招正偏移",
}


def migrate_source_types(db: Session) -> dict[str, Any]:
    updated: dict[str, int] = {}
    for old, new in _MAPPING.items():
        res = db.execute(
            text("UPDATE part SET source_type = :new WHERE source_type = :old"),
            {"old": old, "new": new},
        )
        if res.rowcount:
            updated[f"{old}->{new}"] = res.rowcount
    db.commit()
    if updated:
        logger.info("来源枚举迁移: %s", updated)
    return {"updated": updated}
