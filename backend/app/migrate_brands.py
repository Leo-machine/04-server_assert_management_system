"""品牌适用配件类型。幂等 ALTER + 回填。"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .models import Brand, PartModel, User

logger = logging.getLogger(__name__)

# 存量品牌默认适用类型（按常见货架归类；整机厂/「通用」留空=全类可用）
DEFAULT_BRAND_CATEGORIES: dict[str, list[str]] = {
    "三星": ["内存", "固态硬盘"],
    "海力士": ["内存"],
    "镁光": ["内存", "固态硬盘"],
    "希捷": ["机械硬盘"],
    "西部数据": ["机械硬盘", "固态硬盘"],
    "NVIDIA": ["算力卡"],
    "AMD": ["算力卡"],
    "Intel": ["网卡", "算力卡"],
    "Broadcom": ["RAID卡", "HBA卡", "网卡"],
    "Mellanox": ["网卡"],
    "华为": ["网卡", "光模块", "服务器"],
    "H3C": ["网卡", "光模块", "服务器"],
    "戴尔": [],
    "浪潮": [],
    "联想": [],
    "超微": [],
    "通用": [],
}

# 老库追加回填：品牌后续新增适用类型时并入已有列表（幂等）
_BRAND_CATEGORY_APPEND: dict[str, list[str]] = {
    "华为": ["服务器"],
    "H3C": ["服务器"],
}


def _table_columns(db: Session, table: str) -> set[str]:
    rows = db.execute(text(f"PRAGMA table_info({table})")).all()
    return {r[1] for r in rows}


def migrate_brands(db: Session) -> dict[str, Any]:
    added = False
    cols = _table_columns(db, "brand")
    if "categories" not in cols:
        db.execute(text("ALTER TABLE brand ADD COLUMN categories JSON"))
        added = True

    existing = list(db.scalars(select(Brand)).all())
    by_name = {b.name: b for b in existing}
    created = 0
    users_exist = db.scalars(select(User).limit(1)).first() is not None

    # 升级库：已有用户但品牌表空（seed 被跳过）→ 回填默认名录
    # 新库：无用户时留给 seed，避免与 seed 重复插入
    should_fill_defaults = bool(existing) or users_exist
    if should_fill_defaults:
        for name, cats in DEFAULT_BRAND_CATEGORIES.items():
            if name not in by_name:
                row = Brand(name=name, categories=cats or None)
                db.add(row)
                by_name[name] = row
                created += 1
        if created:
            db.flush()

    # 从型号上的品牌字符串回填缺失名录项
    model_brands = {
        (m.brand or "").strip()
        for m in db.scalars(select(PartModel)).all()
    }
    model_brands.discard("")
    for name in sorted(model_brands):
        if name in by_name:
            continue
        cats = DEFAULT_BRAND_CATEGORIES.get(name)
        row = Brand(name=name, categories=cats or None)
        db.add(row)
        by_name[name] = row
        created += 1
    if created:
        db.flush()

    synced = 0
    for b in by_name.values():
        if b.categories is not None:
            continue
        cats = DEFAULT_BRAND_CATEGORIES.get(b.name)
        if cats is None:
            continue
        b.categories = cats or None
        synced += 1

    # 追加回填：已有列表中并入新增适用类型（幂等）
    appended = 0
    for name, extra in _BRAND_CATEGORY_APPEND.items():
        b = by_name.get(name)
        if b is None or b.categories is None:
            continue  # None=全类可用，无需追加
        missing = [c for c in extra if c not in b.categories]
        if missing:
            b.categories = list(b.categories) + missing
            appended += 1

    db.commit()
    if added or created or synced or appended:
        logger.info(
            "brands 迁移: added_col=%s created=%s synced=%s appended=%s",
            added,
            created,
            synced,
            appended,
        )
    return {"added_col": added, "created": created, "synced": synced, "appended": appended}
