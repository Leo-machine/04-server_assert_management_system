"""可调余量统计（只读）。按规格聚合，便于后续扩展其它品类维度。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import enums
from ..models import Part, PartModel


# 品类 → 分组维度（列名）。后续其它类只在此注册，不重写整套统计。
CATEGORY_GROUP_DIMS: dict[str, tuple[str, ...]] = {
    "内存": ("capacity_gb", "ddr_gen"),
}


def allocatable_summary(
    db: Session,
    *,
    category: Optional[str] = None,
    home_owner_unit: str = enums.HOME_OWNER_UNIT,
) -> list[dict]:
    """
    口径：在库 ∩ 本单位产权 ∩ 通用可调。
    分组：category + 该品类注册的聚合列。
    """
    cats = [category] if category else list(CATEGORY_GROUP_DIMS.keys())
    results: list[dict] = []

    for cat in cats:
        dims = CATEGORY_GROUP_DIMS.get(cat)
        if not dims:
            continue

        dim_cols = [getattr(PartModel, d) for d in dims]
        stmt = (
            select(
                PartModel.category,
                *dim_cols,
                func.count(Part.id).label("allocatable_count"),
            )
            .join(Part, Part.model_id == PartModel.id)
            .where(
                PartModel.category == cat,
                Part.current_status == enums.STATUS_IN_STOCK,
                Part.owner_unit == home_owner_unit,
                Part.allocatable_flag == enums.ALLOC_GENERAL,
            )
            .group_by(PartModel.category, *dim_cols)
            .order_by(PartModel.category, *dim_cols)
        )
        for row in db.execute(stmt).all():
            capacity_gb = row.capacity_gb
            ddr_gen = row.ddr_gen
            label_parts = []
            if capacity_gb is not None:
                label_parts.append(f"{capacity_gb}GB")
            if ddr_gen:
                label_parts.append(ddr_gen)
            results.append(
                {
                    "category": row.category,
                    "capacity_gb": capacity_gb,
                    "ddr_gen": ddr_gen,
                    "spec_label": " ".join(label_parts) or "(规格未填)",
                    "allocatable_count": int(row.allocatable_count),
                    "home_owner_unit": home_owner_unit,
                }
            )
    return results
