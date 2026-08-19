"""一次性清空种子/演示业务数据，保留管理员与已录入的真实库位。

用法（在 backend 目录）：
  .venv/bin/python -m app.clear_demo_data
"""

from __future__ import annotations

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import (
    Approval,
    ApprovalStep,
    ExternalOrg,
    MovementLog,
    Part,
    PartModel,
    PartServerLink,
    Server,
    ServerMovementLog,
    Stocktake,
    StocktakeDiscrepancy,
    StocktakeItem,
    StorageLocation,
    Supplier,
    User,
)

DEMO_USERNAMES = ("zhangyw", "lizz", "wangzg", "zhaojl", "qiancg", "wawei")
DEMO_LOCATIONS = {
    ("一号库房", "A-01"),
    ("一号库房", "C-03"),
    ("A栋数据中心", "Rack-B-03"),
    ("A栋数据中心", "Rack-D-12"),
}


def clear_demo_data(db: Session) -> dict[str, int]:
    counts: dict[str, int] = {}

    def wipe(model) -> None:
        result = db.execute(delete(model))
        counts[model.__tablename__] = result.rowcount or 0

    wipe(StocktakeDiscrepancy)
    wipe(StocktakeItem)
    wipe(Stocktake)
    wipe(ApprovalStep)
    wipe(MovementLog)
    wipe(Approval)
    wipe(PartServerLink)
    wipe(ServerMovementLog)
    wipe(Part)
    wipe(Server)
    wipe(PartModel)
    wipe(Supplier)
    wipe(ExternalOrg)

    loc_ids = [
        loc.id
        for loc in db.scalars(select(StorageLocation)).all()
        if (loc.warehouse, loc.slot) in DEMO_LOCATIONS
    ]
    if loc_ids:
        result = db.execute(delete(StorageLocation).where(StorageLocation.id.in_(loc_ids)))
        counts["storage_location"] = result.rowcount or 0
    else:
        counts["storage_location"] = 0

    result = db.execute(delete(User).where(User.username.in_(DEMO_USERNAMES)))
    counts["user"] = result.rowcount or 0

    seq_exists = db.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
    ).first()
    if seq_exists:
        for table in (
            "stocktake_discrepancy",
            "stocktake_item",
            "stocktake",
            "approval_step",
            "movement_log",
            "approval",
            "part_server_link",
            "server_movement_log",
            "part",
            "server",
            "part_model",
            "supplier",
            "external_org",
        ):
            db.execute(text("DELETE FROM sqlite_sequence WHERE name = :name"), {"name": table})

    db.commit()
    return counts


def main() -> None:
    db = SessionLocal()
    try:
        counts = clear_demo_data(db)
        remaining_users = db.scalars(select(User.username)).all()
        remaining_locs = db.scalar(select(func.count()).select_from(StorageLocation))
        print("cleared:", {k: v for k, v in counts.items() if v})
        print("remaining_users:", remaining_users)
        print("remaining_locations:", remaining_locs)
    finally:
        db.close()


if __name__ == "__main__":
    main()
