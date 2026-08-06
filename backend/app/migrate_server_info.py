"""服务器合同/采购信息字段迁移：幂等 ALTER ADD COLUMN。"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_SERVER_NEW_COLS = [
    ("supplier", "VARCHAR(100)"),
    ("contract_no", "VARCHAR(100)"),
    ("project", "VARCHAR(100)"),
    ("owner_unit", "VARCHAR(100)"),
    ("warranty_expiry", "DATE"),
    ("arrival_date", "DATE"),
    ("purchase_amount", "NUMERIC(12, 2)"),
    ("disk_slot_count", "INTEGER"),
    ("disk_interface", "VARCHAR(50)"),
    ("mem_slot_count", "INTEGER"),
    ("mem_ddr_gens", "VARCHAR(50)"),
    ("pcie_slot_count", "INTEGER"),
    ("nvme_slot_count", "INTEGER"),
    ("nvme_interface", "VARCHAR(50)"),
]


def migrate_server_info(db: Session) -> dict[str, Any]:
    rows = db.execute(text("PRAGMA table_info(server)")).all()
    cols = {r[1] for r in rows}
    added: list[str] = []
    for name, typ in _SERVER_NEW_COLS:
        if name in cols:
            continue
        db.execute(text(f"ALTER TABLE server ADD COLUMN {name} {typ}"))
        added.append(name)
    db.commit()
    if added:
        logger.info("server 信息字段迁移: added=%s", added)
    return {"added": added}
