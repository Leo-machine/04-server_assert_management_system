"""品牌按配件类型归类。"""

from tests.conftest import op_headers


def test_list_brands_filter_by_category(client):
    mem = client.get("/api/brands", params={"category": "内存"}, headers=op_headers(1)).json()
    names = {b["name"] for b in mem}
    assert "三星" in names
    assert "海力士" in names
    assert "希捷" not in names  # 仅机械硬盘
    assert "戴尔" in names  # 通用（未标注）

    disk = client.get("/api/brands", params={"category": "机械硬盘"}, headers=op_headers(1)).json()
    disk_names = {b["name"] for b in disk}
    assert "希捷" in disk_names
    assert "海力士" not in disk_names
    assert "戴尔" in disk_names


def test_create_brand_with_categories(client):
    r = client.post(
        "/api/brands",
        json={"name": "金士顿-测试", "categories": ["内存", "固态硬盘"]},
        headers=op_headers(1),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["categories"] == ["内存", "固态硬盘"]

    mem = client.get("/api/brands", params={"category": "内存"}, headers=op_headers(1)).json()
    assert any(b["name"] == "金士顿-测试" for b in mem)
    raid = client.get("/api/brands", params={"category": "RAID卡"}, headers=op_headers(1)).json()
    assert all(b["name"] != "金士顿-测试" for b in raid)


def test_update_brand_categories(client):
    r = client.post(
        "/api/brands",
        json={"name": "测试归类品牌", "categories": ["网卡"]},
        headers=op_headers(1),
    )
    brand_id = r.json()["id"]
    r2 = client.put(
        f"/api/brands/{brand_id}",
        json={"categories": ["光模块", "网卡"]},
        headers=op_headers(1),
    )
    assert r2.status_code == 200
    assert set(r2.json()["categories"]) == {"光模块", "网卡"}


def test_invalid_category_rejected(client):
    r = client.post(
        "/api/brands",
        json={"name": "坏类型", "categories": ["显卡"]},
        headers=op_headers(1),
    )
    assert r.status_code == 400


def test_migrate_brands_backfills_when_users_exist_but_brand_empty(db_session):
    """升级场景：有用户、品牌表被清空后，migrate_brands 应回填默认名录。"""
    from sqlalchemy import delete, select

    from app.migrate_brands import migrate_brands
    from app.models import Brand, User

    assert db_session.scalars(select(User).limit(1)).first() is not None
    db_session.execute(delete(Brand))
    db_session.commit()
    assert db_session.scalars(select(Brand).limit(1)).first() is None

    result = migrate_brands(db_session)
    assert result["created"] > 0
    names = {b.name for b in db_session.scalars(select(Brand)).all()}
    assert "三星" in names
    assert "海力士" in names
