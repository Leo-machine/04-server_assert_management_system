from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..category_specs import PART_CATEGORIES
from ..models import AssetCategory, Brand, PartModel, Supplier
from .movement import BusinessError


def list_categories(db: Session, *, tree: bool = False) -> list:
    rows = list(
        db.scalars(
            select(AssetCategory).order_by(
                AssetCategory.level, AssetCategory.sort_order, AssetCategory.id
            )
        ).all()
    )
    if not tree:
        return rows
    nodes = {
        row.id: {
            "id": row.id,
            "name": row.name,
            "code": row.code,
            "level": row.level,
            "parent_id": row.parent_id,
            "sort_order": row.sort_order,
            "enabled": bool(row.enabled),
            "business_category": row.business_category,
            "children": [],
        }
        for row in rows
    }
    roots = []
    for row in rows:
        node = nodes[row.id]
        if row.parent_id is None:
            roots.append(node)
        elif row.parent_id in nodes:
            nodes[row.parent_id]["children"].append(node)
    return roots


def get_category(db: Session, category_id: int) -> AssetCategory:
    row = db.get(AssetCategory, category_id)
    if row is None:
        raise BusinessError("资产类别不存在")
    return row


def normalize_level2_ids(
    db: Session, category_ids: Optional[list[int]]
) -> Optional[list[int]]:
    """校验基础数据适用范围，只允许关联启用的二级目录。"""
    if not category_ids:
        return None
    cleaned = list(dict.fromkeys(int(item) for item in category_ids))
    rows = list(
        db.scalars(select(AssetCategory).where(AssetCategory.id.in_(cleaned))).all()
    )
    if len(rows) != len(cleaned):
        raise BusinessError("选择的资产类别不存在")
    invalid = [row.name for row in rows if row.level != 2 or not row.enabled]
    if invalid:
        raise BusinessError(f"只能选择启用的二级资产类别：{'、'.join(invalid)}")
    return cleaned


def normalize_level2_id(db: Session, category_id: Optional[int]) -> Optional[int]:
    values = normalize_level2_ids(db, [category_id] if category_id else None)
    return values[0] if values else None


def _level_for_parent(db: Session, parent_id: Optional[int]) -> int:
    if parent_id is None:
        return 1
    parent = get_category(db, parent_id)
    if parent.level >= 3:
        raise BusinessError("三级类别下不能再新增子类别")
    return parent.level + 1


def _normalize_business(level: int, value: Optional[str]) -> Optional[str]:
    business = (value or "").strip() or None
    if business and level != 3:
        raise BusinessError("仅三级类别可关联已落地的入库品类")
    if business and business not in PART_CATEGORIES:
        raise BusinessError(f"未支持的入库品类：{business}")
    return business


def _generate_code(db: Session, parent_id: Optional[int]) -> str:
    """按父目录编码生成稳定、可读且唯一的类别编码。"""
    if parent_id is None:
        base = "ASSET"
    else:
        parent = get_category(db, parent_id)
        base = parent.code or f"ASSET_{parent.id:03d}"
    sibling_codes = set(
        db.scalars(
            select(AssetCategory.code).where(
                AssetCategory.parent_id.is_(None)
                if parent_id is None
                else AssetCategory.parent_id == parent_id
            )
        ).all()
    )
    index = 1
    while f"{base}_{index:02d}" in sibling_codes:
        index += 1
    return f"{base}_{index:02d}"


def _ensure_unique_sibling(
    db: Session,
    *,
    name: str,
    parent_id: Optional[int],
    exclude_id: Optional[int] = None,
) -> None:
    query = select(AssetCategory.id).where(
        AssetCategory.name == name,
        AssetCategory.parent_id.is_(None)
        if parent_id is None
        else AssetCategory.parent_id == parent_id,
    )
    if exclude_id is not None:
        query = query.where(AssetCategory.id != exclude_id)
    if db.scalars(query.limit(1)).first() is not None:
        raise BusinessError("同级目录下已存在同名类别")


def _ensure_not_descendant(
    db: Session, *, category_id: int, parent_id: Optional[int]
) -> None:
    current_id = parent_id
    visited: set[int] = set()
    while current_id is not None:
        if current_id == category_id:
            raise BusinessError("不能将类别移动到自身的下级目录")
        if current_id in visited:
            raise BusinessError("资产类别目录存在层级循环")
        visited.add(current_id)
        current_id = get_category(db, current_id).parent_id


def _save(db: Session, row: AssetCategory) -> AssetCategory:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise BusinessError("同级目录名、编码或业务映射已存在") from exc
    db.refresh(row)
    return row


def create_category(
    db: Session,
    *,
    name: str,
    code: Optional[str] = None,
    parent_id: Optional[int] = None,
    sort_order: int = 0,
    enabled: bool = True,
    business_category: Optional[str] = None,
) -> AssetCategory:
    clean_name = (name or "").strip()
    if not clean_name:
        raise BusinessError("类别名称必填")
    level = _level_for_parent(db, parent_id)
    _ensure_unique_sibling(db, name=clean_name, parent_id=parent_id)
    clean_code = (code or "").strip() or _generate_code(db, parent_id)
    row = AssetCategory(
        name=clean_name,
        code=clean_code,
        level=level,
        parent_id=parent_id,
        sort_order=sort_order,
        enabled=1 if enabled else 0,
        business_category=_normalize_business(level, business_category),
    )
    db.add(row)
    return _save(db, row)


def update_category(
    db: Session,
    category_id: int,
    **values,
) -> AssetCategory:
    row = get_category(db, category_id)
    name = (values.get("name") or "").strip()
    if not name:
        raise BusinessError("类别名称必填")
    parent_id = values.get("parent_id")
    if parent_id == row.id:
        raise BusinessError("不能将类别设为自身的上级")
    _ensure_not_descendant(db, category_id=row.id, parent_id=parent_id)
    new_level = _level_for_parent(db, parent_id)
    has_children = db.scalars(
        select(AssetCategory.id).where(AssetCategory.parent_id == row.id).limit(1)
    ).first() is not None
    if has_children and new_level != row.level:
        raise BusinessError("该类别已有下级，禁止跨层级移动")
    _ensure_unique_sibling(
        db, name=name, parent_id=parent_id, exclude_id=category_id
    )
    row.name = name
    row.code = (values.get("code") or "").strip() or row.code or _generate_code(db, parent_id)
    row.parent_id = parent_id
    row.level = new_level
    row.sort_order = values.get("sort_order", 0)
    row.enabled = 1 if values.get("enabled", True) else 0
    row.business_category = _normalize_business(
        new_level, values.get("business_category")
    )
    return _save(db, row)


def delete_category(db: Session, category_id: int) -> None:
    row = get_category(db, category_id)
    child = db.scalars(
        select(AssetCategory.id).where(AssetCategory.parent_id == row.id).limit(1)
    ).first()
    if child is not None:
        raise BusinessError("该类别存在下级目录，请先处理下级")
    if row.level == 2:
        model_in_use = db.scalars(
            select(PartModel.id)
            .where(PartModel.asset_category_id == row.id)
            .limit(1)
        ).first()
        brand_in_use = any(
            row.id in (brand.asset_category_ids or [])
            for brand in db.scalars(select(Brand)).all()
        )
        supplier_in_use = any(
            row.id in (supplier.asset_category_ids or [])
            for supplier in db.scalars(select(Supplier)).all()
        )
        if model_in_use is not None or brand_in_use or supplier_in_use:
            raise BusinessError("该类别已被型号、品牌或供应商引用，可停用但不能删除")
    if row.business_category:
        in_use = db.scalars(
            select(PartModel.id)
            .where(PartModel.category == row.business_category)
            .limit(1)
        ).first()
        if in_use is not None:
            raise BusinessError("该类别已关联型号数据，可停用但不能删除")
    db.delete(row)
    db.commit()
