"""Demo 03：可调余量字段 + 内存聚合列。幂等 ALTER。"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import enums
from .models import Part, PartModel
from .services.memory_spec import sync_memory_aggregate_columns

logger = logging.getLogger(__name__)


def _table_columns(db: Session, table: str) -> set[str]:
    rows = db.execute(text(f"PRAGMA table_info({table})")).all()
    return {r[1] for r in rows}


def _add_column_if_missing(db: Session, table: str, col: str, ddl_type: str) -> bool:
    cols = _table_columns(db, table)
    if col in cols:
        return False
    db.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl_type}"))
    return True


def migrate_demo03(db: Session) -> dict[str, Any]:
    added: list[str] = []

    if _add_column_if_missing(db, "user", "role", "VARCHAR(20)"):
        added.append("user.role")
    db.execute(
        text(
            "UPDATE \"user\" SET role = :role "
            "WHERE role IS NULL OR role = ''"
        ),
        {"role": enums.ROLE_OPERATOR},
    )

    if _add_column_if_missing(db, "part_model", "capacity_gb", "INTEGER"):
        added.append("part_model.capacity_gb")
    if _add_column_if_missing(db, "part_model", "ddr_gen", "VARCHAR(20)"):
        added.append("part_model.ddr_gen")

    part_cols = [
        ("supplier", "VARCHAR(100)"),
        ("project", "VARCHAR(100)"),
        ("owner_unit", "VARCHAR(100)"),
        ("warranty_expiry", "DATE"),
        ("allocatable_flag", "VARCHAR(20)"),
    ]
    for name, typ in part_cols:
        if _add_column_if_missing(db, "part", name, typ):
            added.append(f"part.{name}")

    # 回填实物默认值（旧行）
    db.execute(
        text(
            "UPDATE part SET owner_unit = :home "
            "WHERE owner_unit IS NULL OR owner_unit = ''"
        ),
        {"home": enums.HOME_OWNER_UNIT},
    )
    db.execute(
        text(
            "UPDATE part SET allocatable_flag = :flag "
            "WHERE allocatable_flag IS NULL OR allocatable_flag = ''"
        ),
        {"flag": enums.ALLOC_GENERAL},
    )

    # 回填内存聚合列
    models = list(db.scalars(select(PartModel)).all())
    synced = 0
    for m in models:
        before = (m.capacity_gb, m.ddr_gen)
        sync_memory_aggregate_columns(m)
        if (m.capacity_gb, m.ddr_gen) != before:
            synced += 1

    db.commit()
    if added or synced:
        logger.info("demo03 迁移: added=%s memory_synced=%s", added, synced)
    return {"added": added, "memory_synced": synced}
