import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.migrate_brands import migrate_brands
from app.migrate_demo03 import migrate_demo03
from app.migrate_part_models import migrate_legacy_part_models
from app.migrate_suppliers import migrate_suppliers
from app.migrate_wave1 import migrate_wave1
from app.seed import seed_if_empty


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    migrate_wave1(db)
    migrate_demo03(db)
    migrate_brands(db)
    seed_if_empty(db)
    migrate_legacy_part_models(db)
    migrate_demo03(db)
    migrate_brands(db)
    migrate_suppliers(db)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def op_headers(user_id: int) -> dict:
    return {"X-Operator-Id": str(user_id)}
