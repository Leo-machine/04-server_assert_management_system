"""供应商表：幂等建表由 create_all；本脚本回填配件已有供应商名到名录。"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Part, Supplier

logger = logging.getLogger(__name__)


def migrate_suppliers(db: Session) -> dict[str, Any]:
    existing = {s.name for s in db.scalars(select(Supplier)).all()}
    names = {
        (p.supplier or "").strip()
        for p in db.scalars(select(Part).where(Part.supplier.is_not(None))).all()
    }
    names.discard("")
    created = 0
    for name in sorted(names):
        if name in existing:
            continue
        db.add(Supplier(name=name))
        created += 1
    if created:
        db.commit()
        logger.info("suppliers 迁移: created=%s", created)
    return {"created": created}
