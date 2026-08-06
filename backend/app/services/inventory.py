"""可调余量统计（只读）。按规格聚合，便于后续扩展其它品类维度。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import enums
from ..category_specs import PART_CATEGORIES
from ..models import Part, PartModel

# 品类 → 规格分组维度（PartModel 正式列）。未注册的品类回退为按型号聚合。
CATEGORY_GROUP_DIMS: dict[str, tuple[str, ...]] = {
    "内存": ("capacity_gb", "ddr_gen"),
}

ALL_CATEGORIES = PART_CATEGORIES


def allocatable_summary(
    db: Session,
    *,
    category: Optional[str] = None,
    home_owner_unit: str = enums.HOME_OWNER_UNIT,
) -> list[dict]:
    """
    口径：在库 ∩ 本单位产权 ∩ 通用可调。
    分组：注册了规格维度的品类（内存）按规格聚合；其余品类按型号聚合。
    """
    cats = [category] if category else list(ALL_CATEGORIES)
    results: list[dict] = []

    for cat in cats:
        dims = CATEGORY_GROUP_DIMS.get(cat)
        dim_cols = (
            [getattr(PartModel, d) for d in dims] if dims else []
        )
        stmt = (
            select(
                PartModel.id.label("model_id"),
                PartModel.model_name,
                PartModel.category,
                PartModel.capacity_gb,
                PartModel.ddr_gen,
                func.count(Part.id).label("allocatable_count"),
            )
            .join(Part, Part.model_id == PartModel.id)
            .where(
                PartModel.category == cat,
                Part.current_status == enums.STATUS_IN_STOCK,
                Part.owner_unit == home_owner_unit,
                Part.allocatable_flag == enums.ALLOC_GENERAL,
            )
            .group_by(
                PartModel.category,
                *(dim_cols if dims else [PartModel.id]),
            )
            .order_by(PartModel.category, *(dim_cols if dims else [PartModel.id]))
        )

        for row in db.execute(stmt).all():
            if dims:
                label_parts = []
                if row.capacity_gb is not None:
                    label_parts.append(f"{row.capacity_gb}GB")
                if row.ddr_gen:
                    label_parts.append(row.ddr_gen)
                spec_label = " ".join(label_parts) or "(规格未填)"
                results.append(
                    {
                        "category": row.category,
                        "capacity_gb": row.capacity_gb,
                        "ddr_gen": row.ddr_gen,
                        "model_id": None,
                        "spec_label": spec_label,
                        "allocatable_count": int(row.allocatable_count),
                        "home_owner_unit": home_owner_unit,
                    }
                )
            else:
                results.append(
                    {
                        "category": row.category,
                        "capacity_gb": None,
                        "ddr_gen": None,
                        "model_id": row.model_id,
                        "spec_label": row.model_name,
                        "allocatable_count": int(row.allocatable_count),
                        "home_owner_unit": home_owner_unit,
                    }
                )
    return results
