"""Demo 03：可调余量字段 + 内存聚合列 + 用户角色/密码回填。幂等 ALTER。"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import enums
from .models import PartModel, User
from .services.memory_spec import sync_memory_aggregate_columns

logger = logging.getLogger(__name__)

DEFAULT_DEMO_PASSWORD = "123456"
DEFAULT_DEMO_PASSWORD_HASH = hashlib.sha256(DEFAULT_DEMO_PASSWORD.encode()).hexdigest()

# role_label / 旧 role 文本 → 权限角色
_LABEL_TO_ROLE = {
    "运维": enums.ROLE_OPERATIONS,
    "仓管": enums.ROLE_OPERATIONS,
    "组长": enums.ROLE_LEADER,
    "主管": enums.ROLE_LEADER,
    "经理": enums.ROLE_LEADER,
    "管理员": enums.ROLE_LEADER,
    "审批人": enums.ROLE_LEADER,
    "操作员": enums.ROLE_OPERATIONS,
}

# 已知种子用户的登录账号（老库 username 为空时按 name 回填）
_USERNAME_BY_NAME = {
    "admin": "admin",
    "张运维": "zhangyw",
    "李组长": "lizz",
    "王主管": "wangzg",
    "赵经理": "zhaojl",
    "钱仓管": "qiancg",
}


def _table_columns(db: Session, table: str) -> set[str]:
    rows = db.execute(text(f"PRAGMA table_info({table})")).all()
    return {r[1] for r in rows}


def _add_column_if_missing(db: Session, table: str, col: str, ddl_type: str) -> bool:
    cols = _table_columns(db, table)
    if col in cols:
        return False
    db.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl_type}"))
    return True


def _resolve_role(u: User) -> str:
    name = (u.name or "").strip().lower()
    if name == "admin":
        return enums.ROLE_LEADER
    label = (u.role_label or "").strip()
    if label in _LABEL_TO_ROLE:
        return _LABEL_TO_ROLE[label]
    current = (u.role or "").strip()
    if current in enums.ROLES:
        return current
    if current in _LABEL_TO_ROLE:
        return _LABEL_TO_ROLE[current]
    return enums.ROLE_OPERATIONS


def _backfill_user_roles(db: Session) -> int:
    """仅纠正空/非法角色；不覆盖已有合法角色（避免重启打回人工调整）。"""
    updated = 0
    users = list(db.scalars(select(User)).all())
    for u in users:
        current = (u.role or "").strip()
        if current in enums.ROLES:
            continue
        u.role = _resolve_role(u)
        updated += 1
    return updated


def _backfill_usernames(db: Session) -> int:
    """老库 username 为空：按已知种子映射回填，未知用户兜底 user{id}。"""
    updated = 0
    for u in db.scalars(select(User)).all():
        if (u.username or "").strip():
            continue
        u.username = _USERNAME_BY_NAME.get((u.name or "").strip()) or f"user{u.id}"
        updated += 1
    return updated


def _backfill_passwords(db: Session) -> int:
    """无密码用户回填演示密码 123456。"""
    updated = 0
    for u in db.scalars(select(User)).all():
        if not u.password_hash:
            u.password_hash = DEFAULT_DEMO_PASSWORD_HASH
            updated += 1
    return updated


def migrate_demo03(db: Session) -> dict[str, Any]:
    added: list[str] = []

    if _add_column_if_missing(db, "user", "role", "VARCHAR(20)"):
        added.append("user.role")
    if _add_column_if_missing(db, "user", "password_hash", "VARCHAR(128)"):
        added.append("user.password_hash")
    if _add_column_if_missing(db, "user", "username", "VARCHAR(50)"):
        added.append("user.username")
    db.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_username "
            "ON user (username)"
        )
    )
    usernames_fixed = _backfill_usernames(db)
    roles_fixed = _backfill_user_roles(db)
    passwords_fixed = _backfill_passwords(db)

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

    # 回填内存聚合列（脏数据跳过，不拖垮启动）
    models = list(db.scalars(select(PartModel)).all())
    synced = 0
    skipped = 0
    for m in models:
        before = (m.capacity_gb, m.ddr_gen)
        if m.category == "内存":
            gen = (m.spec or {}).get("内存类型")
            if gen not in enums.DDR_GENS:
                skipped += 1
                logger.warning(
                    "demo03 跳过脏内存型号 id=%s model=%s 代际=%r",
                    m.id,
                    m.model_name,
                    gen,
                )
        sync_memory_aggregate_columns(m, strict=False)
        if (m.capacity_gb, m.ddr_gen) != before:
            synced += 1

    db.commit()
    if added or synced or roles_fixed or passwords_fixed or skipped or usernames_fixed:
        logger.info(
            "demo03 迁移: added=%s memory_synced=%s roles_fixed=%s "
            "passwords_fixed=%s usernames_fixed=%s memory_skipped=%s",
            added,
            synced,
            roles_fixed,
            passwords_fixed,
            usernames_fixed,
            skipped,
        )
    return {
        "added": added,
        "memory_synced": synced,
        "roles_fixed": roles_fixed,
        "passwords_fixed": passwords_fixed,
        "usernames_fixed": usernames_fixed,
        "memory_skipped": skipped,
    }
