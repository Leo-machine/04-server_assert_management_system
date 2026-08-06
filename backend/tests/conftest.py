import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.migrate_brands import migrate_brands
from app.migrate_demo03 import migrate_demo03
from app.migrate_part_models import migrate_legacy_part_models
from app.migrate_suppliers import migrate_suppliers
from app.migrate_user_status import migrate_user_status
from app.migrate_wave1 import migrate_wave1
from app.seed import seed_if_empty


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    migrate_wave1(db)
    migrate_user_status(db)
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
    """测试登录态：铸造真实签名令牌（业务接口已不再接受 X-Operator-Id）。"""
    from app.deps import make_token
    from app.models import User

    user = User(id=user_id)
    return {"Authorization": f"Bearer {make_token(user)}"}



def demo_cast(client) -> dict:
    """按姓名取演示角色，避免种子顺序变化导致下标错位。"""
    login = client.post("/api/auth/login", json={"username": "zhangyw", "password": "123456"})
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    by_name = {u["name"]: u for u in client.get("/api/users", headers=h).json()}
    required = ("张运维", "李组长", "王主管", "赵经理", "钱仓管")
    missing = [n for n in required if n not in by_name]
    assert not missing, f"种子用户缺失: {missing}"
    return {
        "applicant": by_name["张运维"],
        "a1": by_name["李组长"],
        "a2": by_name["王主管"],
        "a3": by_name["赵经理"],
        "other": by_name["钱仓管"],
        "admin": by_name.get("admin") or by_name.get("系统管理员"),
        "approver_ids": [
            by_name["李组长"]["id"],
            by_name["王主管"]["id"],
            by_name["赵经理"]["id"],
        ],
        "users": list(by_name.values()),
        "headers": h,
    }
