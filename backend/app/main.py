from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import DB_PATH, Base, SessionLocal, engine
from .migrate_brands import migrate_brands
from .migrate_approval_uniqueness import migrate_approval_uniqueness
from .migrate_asset_categories import migrate_asset_categories
from .migrate_catalog_scopes import migrate_catalog_scopes
from .migrate_demo03 import migrate_demo03
from .migrate_part_models import migrate_legacy_part_models
from .migrate_server_info import migrate_server_info
from .migrate_source_types import migrate_source_types
from .migrate_user_status import migrate_user_status
from .migrate_suppliers import migrate_suppliers
from .migrate_wave1 import migrate_wave1
from .routers import (
    approvals,
    asset_categories,
    auth,
    brands,
    catalog,
    inventory,
    locations,
    part_models,
    parts,
    stocktakes,
    suppliers,
)
from .seed import seed_if_empty


def _ensure_sqlite_file() -> None:
    """避免删除库后留下 0 字节空文件，导致 create_all/查询全挂。"""
    if DB_PATH.exists() and DB_PATH.stat().st_size == 0:
        DB_PATH.unlink()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_sqlite_file()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 结构性迁移（ALTER 加列）必须最先跑——后续数据迁移/seed 按当前 ORM 查询
        migrate_wave1(db)
        migrate_server_info(db)
        migrate_user_status(db)
        migrate_approval_uniqueness(db)
        migrate_asset_categories(db)
        migrate_catalog_scopes(db)
        # 数据级迁移与 seed
        migrate_demo03(db)
        migrate_brands(db)
        seed_if_empty(db)
        migrate_legacy_part_models(db)
        # 遗留规格修复后再次同步内存聚合列
        migrate_demo03(db)
        migrate_brands(db)
        migrate_suppliers(db)
        migrate_catalog_scopes(db)
        migrate_source_types(db)
    finally:
        db.close()
    yield


app = FastAPI(title="电网资产及其配件数字化运营系统", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(asset_categories.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")
app.include_router(part_models.router, prefix="/api")
app.include_router(parts.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(approvals.router, prefix="/api")
app.include_router(brands.router, prefix="/api")
app.include_router(suppliers.router, prefix="/api")
app.include_router(locations.router, prefix="/api")
app.include_router(stocktakes.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
