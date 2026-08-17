"""为型号、品牌和供应商补充二级资产类别归属。"""

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from .models import AssetCategory, PartModel


def migrate_catalog_scopes(db: Session) -> None:
    inspector = inspect(db.bind)
    additions = {
        "part_model": ("asset_category_id", "INTEGER"),
        "brand": ("asset_category_ids", "JSON"),
        "supplier": ("asset_category_ids", "JSON"),
    }
    for table, (column, kind) in additions.items():
        columns = {item["name"] for item in inspector.get_columns(table)}
        if column not in columns:
            db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {kind}"))
    db.commit()

    server = db.scalars(
        select(AssetCategory).where(
            AssetCategory.level == 2, AssetCategory.code == "DIGITAL_SERVER"
        )
    ).first()
    if server is not None:
        for model in db.scalars(
            select(PartModel).where(PartModel.asset_category_id.is_(None))
        ).all():
            model.asset_category_id = server.id
        db.commit()
