"""供应商名录。"""

from tests.conftest import op_headers


def test_supplier_crud_and_rename_cascade(client):
    r = client.post(
        "/api/suppliers",
        json={
            "name": "测试供应商A",
            "contact": "小李",
            "contact_info": "13900000001",
        },
        headers=op_headers(1),
    )
    assert r.status_code == 200
    sid = r.json()["id"]

    models = client.get("/api/part-models", headers=op_headers(1)).json()
    mem = next(m for m in models if m["category"] == "内存")
    locs = client.get("/api/storage-locations", headers=op_headers(1)).json()
    inbound = client.post(
        "/api/parts/inbound",
        json={
            "model_id": mem["id"],
            "fixed_asset_no": "FA-SUP-TEST-1",
            "storage_location_id": locs[0]["id"],
            "source_type": "独立合同采购",
            "responsible_group": "基础组",
            "serial_no": "SN-SUP-TEST-1",
            "contract_no": "HT-SUP-TEST",
            "purchase_amount": 500.00,
            "purchase_date": "2026-01-01",
            "sensitivity": "无",
            "supplier": "测试供应商A",
            "project": "测试项目",
            "owner_unit": "本单位信息中心",
            "warranty_expiry": "2029-01-01",
            "allocatable_flag": "通用可调",
            "remark": "测试入库",
        },
        headers=op_headers(1),
    )
    assert inbound.status_code == 200

    supplier_rows = client.get("/api/suppliers", headers=op_headers(1)).json()
    supplier_row = next(row for row in supplier_rows if row["id"] == sid)
    assert supplier_row["usage_count"] == 1

    r2 = client.put(
        f"/api/suppliers/{sid}",
        json={"name": "测试供应商B"},
        headers=op_headers(1),
    )
    assert r2.status_code == 200
    part = client.get(
        f"/api/parts/{inbound.json()['id']}", headers=op_headers(1)
    ).json()
    assert part["supplier"] == "测试供应商B"

    blocked = client.delete(f"/api/suppliers/{sid}", headers=op_headers(1))
    assert blocked.status_code == 400
    assert "引用" in blocked.json()["detail"]


def test_supplier_duplicate_rejected(client):
    client.post(
        "/api/suppliers",
        json={"name": "重复供应商"},
        headers=op_headers(1),
    )
    r = client.post(
        "/api/suppliers",
        json={"name": "重复供应商"},
        headers=op_headers(1),
    )
    assert r.status_code == 400
