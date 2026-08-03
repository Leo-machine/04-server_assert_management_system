"""服务器品类：型号/品牌目录可管理服务器条目，但不走配件入库。"""

from tests.conftest import demo_cast, op_headers


def test_create_server_model(client):
    cast = demo_cast(client)
    r = client.post(
        "/api/part-models",
        json={
            "category": "服务器",
            "model_name": "华为 2288H V6",
            "brand": "华为",
            "spec": {"机型高度U": 2, "CPU型号": "Kunpeng 920", "CPU颗数": 2, "内存插槽数": 32, "盘位数": 12},
        },
        headers=op_headers(cast["admin"]["id"]),
    )
    assert r.status_code == 200, r.json()
    assert r.json()["category"] == "服务器"


def test_server_model_requires_height(client):
    cast = demo_cast(client)
    r = client.post(
        "/api/part-models",
        json={"category": "服务器", "model_name": "测试机型", "spec": {}},
        headers=op_headers(cast["admin"]["id"]),
    )
    assert r.status_code == 400
    assert "机型高度" in r.json()["detail"]


def test_categories_schema_includes_server(client):
    cats = client.get("/api/categories").json()
    names = [c["category"] for c in cats]
    assert "服务器" in names
    assert len(names) == 9


def test_server_category_blocked_from_parts_inbound(client):
    cast = demo_cast(client)
    mid = client.post(
        "/api/part-models",
        json={"category": "服务器", "model_name": "浪潮 NF5280M6 整机", "spec": {"机型高度U": 2}},
        headers=op_headers(cast["admin"]["id"]),
    ).json()["id"]
    loc_id = client.get("/api/storage-locations").json()[0]["id"]
    r = client.post(
        "/api/parts/inbound",
        json={
            "model_id": mid,
            "fixed_asset_no": "FA-SRV-CAT-001",
            "source_type": "独立合同采购",
            "storage_location_id": loc_id,
            "responsible_group": "基础组",
            "serial_no": "SN-SRV-CAT-001",
            "contract_no": "HT-1",
            "purchase_amount": 1000,
            "purchase_date": "2026-08-01",
            "supplier": "通用",
            "project": "测试",
            "owner_unit": "本单位信息中心",
            "warranty_expiry": "2029-01-01",
            "allocatable_flag": "通用可调",
            "remark": "试图把服务器当配件入库",
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 400
    assert "服务器管理" in r.json()["detail"]


def test_brand_huawei_applies_to_server(client):
    """华为品牌适用类型应包含服务器（迁移回填）。"""
    brands = client.get("/api/brands?category=服务器").json()
    names = {b["name"] for b in brands}
    assert "华为" in names
    # 通用品牌（categories 为空）天然适用全部类型
    assert "戴尔" in names
