from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..category_specs import (
    SpecValidationError,
    validate_and_normalize_spec,
    validate_category,
)
from ..models import Part, PartModel
from .memory_spec import sync_memory_aggregate_columns
from .movement import BusinessError
from .asset_categories import normalize_level2_id


def _spec_or_raise(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except SpecValidationError as e:
        raise BusinessError(e.message) from e


def _model_in_use(db: Session, model_id: int) -> bool:
    return (
        db.scalars(select(Part.id).where(Part.model_id == model_id).limit(1)).first()
        is not None
    )


def list_models(db: Session, category: Optional[str] = None) -> list[PartModel]:
    stmt = select(PartModel).order_by(PartModel.category, PartModel.id)
    if category:
        _spec_or_raise(validate_category, category)
        stmt = stmt.where(PartModel.category == category)
    return list(db.scalars(stmt).all())


def get_model(db: Session, model_id: int) -> PartModel:
    model = db.get(PartModel, model_id)
    if model is None:
        raise BusinessError("型号不存在")
    return model


def create_model(
    db: Session,
    *,
    category: str,
    model_name: str,
    brand: Optional[str] = None,
    pn: Optional[str] = None,
    spec: Optional[dict] = None,
    asset_category_id: Optional[int] = None,
) -> PartModel:
    _spec_or_raise(validate_category, category)
    name = (model_name or "").strip()
    if not name:
        raise BusinessError("型号名称必填")
    dup = db.scalars(
        select(PartModel).where(
            PartModel.category == category,
            PartModel.model_name == name,
        )
    ).first()
    if dup is not None:
        raise BusinessError(f"同类型下已存在型号「{name}」")
    normalized = _spec_or_raise(validate_and_normalize_spec, category, spec)
    row = PartModel(
        category=category,
        model_name=name,
        brand=(brand or None),
        pn=(pn or None),
        spec=normalized,
        asset_category_id=normalize_level2_id(db, asset_category_id),
    )
    sync_memory_aggregate_columns(row, normalized)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_model(
    db: Session,
    model_id: int,
    *,
    category: Optional[str] = None,
    model_name: Optional[str] = None,
    brand: Optional[str] = None,
    pn: Optional[str] = None,
    spec: Optional[dict] = None,
    asset_category_id: Optional[int] = None,
) -> PartModel:
    row = get_model(db, model_id)
    old_category = row.category
    new_category = category if category is not None else old_category
    _spec_or_raise(validate_category, new_category)

    category_changed = new_category != old_category
    if category_changed and _model_in_use(db, model_id):
        raise BusinessError("该型号已有入库实物，禁止变更配件类型")

    if model_name is not None:
        name = model_name.strip()
        if not name:
            raise BusinessError("型号名称必填")
        dup = db.scalars(
            select(PartModel).where(
                PartModel.category == new_category,
                PartModel.model_name == name,
                PartModel.id != model_id,
            )
        ).first()
        if dup is not None:
            raise BusinessError(f"同类型下已存在型号「{name}」")
        row.model_name = name

    row.category = new_category
    if brand is not None:
        row.brand = brand or None
    if pn is not None:
        row.pn = pn or None
    if asset_category_id is not None:
        row.asset_category_id = normalize_level2_id(db, asset_category_id)

    # 显式提交 spec，或类型变更时，才重规范化（避免误删未知键）
    if spec is not None or category_changed:
        source_spec = spec if spec is not None else row.spec
        row.spec = _spec_or_raise(
            validate_and_normalize_spec, new_category, source_spec
        )
        sync_memory_aggregate_columns(row, row.spec)

    db.commit()
    db.refresh(row)
    return row


def delete_model(db: Session, model_id: int) -> None:
    row = get_model(db, model_id)
    if _model_in_use(db, model_id):
        raise BusinessError("该型号已有入库实物，禁止删除（可先调整实物型号）")
    db.delete(row)
    db.commit()
