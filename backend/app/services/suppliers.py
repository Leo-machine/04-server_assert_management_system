from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Part, Supplier
from .movement import BusinessError
from .asset_categories import normalize_level2_ids


def list_suppliers(db: Session) -> list[Supplier]:
    rows = list(db.scalars(select(Supplier).order_by(Supplier.name)).all())
    usage = dict(
        db.execute(
            select(Part.supplier, func.count(Part.id))
            .where(Part.supplier.is_not(None))
            .group_by(Part.supplier)
        ).all()
    )
    for row in rows:
        row.usage_count = int(usage.get(row.name, 0))
    return rows


def _supplier_in_use(db: Session, name: str) -> bool:
    return (
        db.scalars(select(Part.id).where(Part.supplier == name).limit(1)).first()
        is not None
    )


def create_supplier(
    db: Session,
    *,
    name: str,
    contact: Optional[str] = None,
    contact_info: Optional[str] = None,
    remark: Optional[str] = None,
    asset_category_ids: Optional[list[int]] = None,
) -> Supplier:
    name = name.strip()
    if not name:
        raise BusinessError("供应商名称必填")
    existing = db.scalars(select(Supplier).where(Supplier.name == name)).first()
    if existing is not None:
        raise BusinessError(f"供应商「{name}」已存在")
    row = Supplier(
        name=name,
        contact=(contact or "").strip() or None,
        contact_info=(contact_info or "").strip() or None,
        remark=(remark or "").strip() or None,
        asset_category_ids=normalize_level2_ids(db, asset_category_ids),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_supplier(
    db: Session,
    supplier_id: int,
    *,
    name: Optional[str] = None,
    contact: Optional[str] = None,
    contact_info: Optional[str] = None,
    remark: Optional[str] = None,
    set_contact: bool = False,
    set_contact_info: bool = False,
    set_remark: bool = False,
    asset_category_ids: Optional[list[int]] = None,
    set_asset_category_ids: bool = False,
) -> Supplier:
    row = db.get(Supplier, supplier_id)
    if row is None:
        raise BusinessError("供应商不存在")

    if name is not None:
        new_name = name.strip()
        if not new_name:
            raise BusinessError("供应商名称必填")
        dup = db.scalars(
            select(Supplier).where(Supplier.name == new_name, Supplier.id != supplier_id)
        ).first()
        if dup is not None:
            raise BusinessError(f"供应商「{new_name}」已存在")
        old_name = row.name
        row.name = new_name
        if new_name != old_name:
            parts = db.scalars(select(Part).where(Part.supplier == old_name)).all()
            for p in parts:
                p.supplier = new_name

    if set_contact:
        row.contact = (contact or "").strip() or None
    if set_contact_info:
        row.contact_info = (contact_info or "").strip() or None
    if set_remark:
        row.remark = (remark or "").strip() or None
    if set_asset_category_ids:
        row.asset_category_ids = normalize_level2_ids(db, asset_category_ids)

    db.commit()
    db.refresh(row)
    return row


def delete_supplier(db: Session, supplier_id: int) -> None:
    row = db.get(Supplier, supplier_id)
    if row is None:
        raise BusinessError("供应商不存在")
    if _supplier_in_use(db, row.name):
        raise BusinessError(f"供应商「{row.name}」已有配件引用，禁止删除")
    db.delete(row)
    db.commit()
