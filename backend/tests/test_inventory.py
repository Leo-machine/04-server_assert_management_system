"""Demo 03：可调余量口径与公共字段。"""

from app import enums
from tests.conftest import op_headers


def _mem_row(rows):
    assert len(rows) == 1
    return rows[0]


def test_allocatable_summary_seed_baseline(client):
    """种子：1001+2001 计入；1002 保留 / 1003 在用 / 1004 外单位 不计。"""
    r = client.get("/api/inventory/allocatable-summary", headers=op_headers(1), params={"category": "内存"})
    assert r.status_code == 200
    row = _mem_row(r.json())
    assert row["capacity_gb"] == 32
    assert row["ddr_gen"] == "DDR4"
    assert row["spec_label"] == "32GB DDR4"
    assert row["allocatable_count"] == 2
    assert row["home_owner_unit"] == enums.HOME_OWNER_UNIT


def test_allocatable_cross_model_aggregation(client):
    """同规格不同品牌型号合并为一行。"""
    models = client.get("/api/part-models", headers=op_headers(1)).json()
    mem = [m for m in models if m["category"] == "内存"]
    assert len(mem) >= 2
    brands = {m["brand"] for m in mem if m["capacity_gb"] == 32 and m["ddr_gen"] == "DDR4"}
    assert "三星" in brands and "海力士" in brands

    rows = client.get("/api/inventory/allocatable-summary", headers=op_headers(1), params={"category": "内存"}).json()
    assert len(rows) == 1
    assert rows[0]["allocatable_count"] == 2


def test_reserve_flag_reduces_count(client):
    parts = client.get("/api/parts", headers=op_headers(1)).json()
    target = next(p for p in parts if p["fixed_asset_no"] == "FA-MEM-1001")
    assert target["allocatable_flag"] == enums.ALLOC_GENERAL

    before = _mem_row(
        client.get("/api/inventory/allocatable-summary", headers=op_headers(1), params={"category": "内存"}).json()
    )["allocatable_count"]

    r = client.patch(
        f"/api/parts/{target['id']}",
        json={"allocatable_flag": enums.ALLOC_RESERVED},
        headers=op_headers(1),
    )
    assert r.status_code == 200
    assert r.json()["allocatable_flag"] == enums.ALLOC_RESERVED

    after = _mem_row(
        client.get("/api/inventory/allocatable-summary", headers=op_headers(1), params={"category": "内存"}).json()
    )["allocatable_count"]
    assert after == before - 1


def test_alloc_flag_blocked_when_not_in_stock(client):
    parts = client.get("/api/parts", headers=op_headers(1)).json()
    in_use = next(p for p in parts if p["fixed_asset_no"] == "FA-MEM-1003")
    assert in_use["current_status"] == enums.STATUS_IN_USE
    r = client.patch(
        f"/api/parts/{in_use['id']}",
        json={"allocatable_flag": enums.ALLOC_RESERVED},
        headers=op_headers(1),
    )
    assert r.status_code == 400
    assert "在库" in r.json()["detail"]


def test_install_reduces_allocatable(client):
    parts = client.get("/api/parts", headers=op_headers(1)).json()
    target = next(p for p in parts if p["fixed_asset_no"] == "FA-MEM-1001")
    servers = client.get("/api/servers", headers=op_headers(1)).json()
    idle = next(s for s in servers if s["run_status"] == enums.RUN_NOT_LIVE)

    before = _mem_row(
        client.get("/api/inventory/allocatable-summary", headers=op_headers(1), params={"category": "内存"}).json()
    )["allocatable_count"]

    r = client.post(
        f"/api/parts/{target['id']}/install",
        json={"server_id": idle["id"], "slot": "DIMM_B1"},
        headers=op_headers(1),
    )
    assert r.status_code == 200
    assert r.json()["current_status"] == enums.STATUS_IN_USE

    after = _mem_row(
        client.get("/api/inventory/allocatable-summary", headers=op_headers(1), params={"category": "内存"}).json()
    )["allocatable_count"]
    assert after == before - 1


def test_inbound_public_fields_and_invalid_flag(client):
    models = client.get("/api/part-models", headers=op_headers(1)).json()
    mem = next(m for m in models if m["category"] == "内存")
    locs = client.get("/api/storage-locations", headers=op_headers(1)).json()

    base = {
        "model_id": mem["id"],
        "storage_location_id": locs[0]["id"],
        "source_type": "独立合同采购",
        "responsible_group": "基础组",
        "serial_no": "SN-TEST-001",
        "contract_no": "HT-TEST-001",
        "purchase_amount": 500.00,
        "purchase_date": "2026-01-01",
        "sensitivity": "无",
        "supplier": "通用配件供应商",
        "project": "Demo03",
        "owner_unit": enums.HOME_OWNER_UNIT,
        "warranty_expiry": "2030-06-01",
        "allocatable_flag": enums.ALLOC_GENERAL,
        "remark": "测试",
    }

    bad = client.post(
        "/api/parts/inbound",
        json={**base, "fixed_asset_no": "FA-MEM-BAD-FLAG", "allocatable_flag": "随便调"},
        headers=op_headers(1),
    )
    assert bad.status_code == 400

    ok = client.post(
        "/api/parts/inbound",
        json={**base, "fixed_asset_no": "FA-MEM-NEW-9001"},
        headers=op_headers(1),
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["supplier"] == "通用配件供应商"
    assert body["project"] == "Demo03"
    assert body["owner_unit"] == enums.HOME_OWNER_UNIT
    assert body["warranty_expiry"] == "2030-06-01"
    assert body["allocatable_flag"] == enums.ALLOC_GENERAL

    count = _mem_row(
        client.get("/api/inventory/allocatable-summary", headers=op_headers(1), params={"category": "内存"}).json()
    )["allocatable_count"]
    assert count == 3  # seed 2 + 新入库


def test_memory_model_syncs_aggregate_columns(client):
    r = client.post(
        "/api/part-models",
        json={
            "category": "内存",
            "model_name": "测试 64GB DDR5",
            "brand": "测试",
            "spec": {"容量GB": 64, "内存类型": "DDR5", "频率MHz": 4800},
        },
        headers=op_headers(1),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["capacity_gb"] == 64
    assert body["ddr_gen"] == "DDR5"
