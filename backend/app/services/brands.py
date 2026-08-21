from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..category_specs import ALL_MANAGED_CATEGORIES, PART_CATEGORIES, SERVER_CATEGORY
from ..models import AssetCategory, Brand, PartModel
from .movement import BusinessError
from .asset_categories import normalize_level2_ids


def _normalize_categories(categories: Optional[list[str]]) -> Optional[list[str]]:
    if categories is None:
        return None
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in categories:
        cat = (raw or "").strip()
        if not cat:
            continue
        if cat not in PART_CATEGORIES:
            raise BusinessError(
                f"非法三级类型「{cat}」，允许：{' / '.join(PART_CATEGORIES)}"
            )
        if cat not in seen:
            cleaned.append(cat)
            seen.add(cat)
    return cleaned or None


def brand_matches_category(
    brand: Brand, category: str, *, device_scope_id: Optional[int] = None
) -> bool:
    """二级范围管理设备品牌，三级类型管理配件品牌。"""
    cats = brand.categories or []
    scopes = brand.asset_category_ids or []
    if category == SERVER_CATEGORY:
        # 全局通用品牌，或明确归属服务器类的设备品牌。
        return (not cats and not scopes) or (
            device_scope_id is not None and device_scope_id in scopes
        )
    if not cats:
        # 有二级范围但无三级类型时，表示仅作为设备整机品牌。
        return not scopes
    return category in cats


def list_brands(db: Session, *, category: Optional[str] = None) -> list[Brand]:
    rows = list(db.scalars(select(Brand).order_by(Brand.name)).all())
    if not category:
        return rows
    if category not in ALL_MANAGED_CATEGORIES:
        raise BusinessError(
            f"非法配件类型「{category}」，允许：{' / '.join(ALL_MANAGED_CATEGORIES)}"
        )
    device_scope_id = None
    if category == SERVER_CATEGORY:
        device_scope_id = db.scalars(
            select(AssetCategory.id).where(
                AssetCategory.level == 2,
                AssetCategory.code == "DIGITAL_SERVER",
            )
        ).first()
    return [
        b
        for b in rows
        if brand_matches_category(b, category, device_scope_id=device_scope_id)
    ]


def _brand_in_use(db: Session, brand_name: str) -> bool:
    return (
        db.scalars(
            select(PartModel.id).where(PartModel.brand == brand_name).limit(1)
        ).first()
        is not None
    )


def create_brand(
    db: Session,
    *,
    name: str,
    categories: Optional[list[str]] = None,
    asset_category_ids: Optional[list[int]] = None,
) -> Brand:
    name = name.strip()
    if not name:
        raise BusinessError("品牌名称必填")
    existing = db.scalars(select(Brand).where(Brand.name == name)).first()
    if existing is not None:
        raise BusinessError(f"品牌「{name}」已存在")
    row = Brand(
        name=name,
        categories=_normalize_categories(categories),
        asset_category_ids=normalize_level2_ids(db, asset_category_ids),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_brand(
    db: Session,
    brand_id: int,
    *,
    name: Optional[str] = None,
    categories: Optional[list[str]] = None,
    set_categories: bool = False,
    asset_category_ids: Optional[list[int]] = None,
    set_asset_category_ids: bool = False,
) -> Brand:
    row = db.get(Brand, brand_id)
    if row is None:
        raise BusinessError("品牌不存在")

    if name is not None:
        new_name = name.strip()
        if not new_name:
            raise BusinessError("品牌名称必填")
        dup = db.scalars(
            select(Brand).where(Brand.name == new_name, Brand.id != brand_id)
        ).first()
        if dup is not None:
            raise BusinessError(f"品牌「{new_name}」已存在")
        old_name = row.name
        row.name = new_name
        if new_name != old_name:
            models = db.scalars(
                select(PartModel).where(PartModel.brand == old_name)
            ).all()
            for m in models:
                m.brand = new_name

    if set_categories:
        row.categories = _normalize_categories(categories)
    if set_asset_category_ids:
        row.asset_category_ids = normalize_level2_ids(db, asset_category_ids)

    db.commit()
    db.refresh(row)
    return row


def delete_brand(db: Session, brand_id: int) -> None:
    row = db.get(Brand, brand_id)
    if row is None:
        raise BusinessError("品牌不存在")
    if _brand_in_use(db, row.name):
        raise BusinessError(f"品牌「{row.name}」已有型号引用，禁止删除")
    db.delete(row)
    db.commit()
