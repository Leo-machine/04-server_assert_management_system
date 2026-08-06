"""入库来源三选：服务器原装绑定联动 / 独立合同采购 / 框招正偏移。"""

from app import enums
from tests.conftest import demo_cast, op_headers


def _mem_model_id(client) -> int:
    models = client.get("/api/part-models", headers=op_headers(1)).json()
    return next(m for m in models if m["category"] == "内存")["id"]


def test_original_inbound_binds_server(client):
    cast = demo_cast(client)
    servers = client.get("/api/servers", headers=op_headers(1)).json()
    idle = next(s for s in servers if s["asset_no"] == "SRV-IDLE-002")

    r = client.post(
        "/api/parts/inbound",
        json={
            "model_id": _mem_model_id(client),
            "fixed_asset_no": "FA-ORIG-001",
            "source_type": "服务器原装",
            "server_id": idle["id"],
            "serial_no": "SN-ORIG-001",
            "purchase_amount": 800.00,
            "allocatable_flag": "通用可调",
            "remark": "随服务器到货",
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 200, r.json()
    part = r.json()
    # 服务器档案带出
    assert part["current_status"] == enums.STATUS_IN_USE
    assert part["current_loc_kind"] == enums.LOC_SERVER
    assert part["current_loc_id"] == idle["id"]
    assert part["supplier"] == idle["supplier"]
    assert part["contract_no"] == idle["contract_no"]
    assert part["responsible_group"] == idle["responsible_group"]
    assert part["source_type"] == "服务器原装"

    # 履历：入库直接到在用/服务器
    moves = client.get(f"/api/parts/{part['id']}/movements", headers=op_headers(1)).json()
    assert len(moves) == 1
    assert moves[0]["event_type"] == "入库"
    assert moves[0]["status_to"] == enums.STATUS_IN_USE
    assert moves[0]["loc_to_kind"] == enums.LOC_SERVER


def test_original_inbound_requires_server(client):
    cast = demo_cast(client)
    r = client.post(
        "/api/parts/inbound",
        json={
            "model_id": _mem_model_id(client),
            "fixed_asset_no": "FA-ORIG-002",
            "source_type": "服务器原装",
            "serial_no": "SN-ORIG-002",
            "purchase_amount": 800.00,
            "allocatable_flag": "通用可调",
            "remark": "缺服务器",
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 400
    assert "关联服务器" in r.json()["detail"]



def test_contract_inbound_manual_fields(client):
    cast = demo_cast(client)
    loc_id = client.get("/api/storage-locations", headers=op_headers(1)).json()[0]["id"]
    r = client.post(
        "/api/parts/inbound",
        json={
            "model_id": _mem_model_id(client),
            "fixed_asset_no": "FA-CT-001",
            "source_type": "独立合同采购",
            "storage_location_id": loc_id,
            "responsible_group": "运营组",
            "serial_no": "SN-CT-001",
            "contract_no": "HT-2026-300",
            "purchase_amount": 1200.00,
            "purchase_date": "2026-08-01",
            "supplier": "通用配件供应商",
            "project": "2026年扩容",
            "owner_unit": "本单位信息中心",
            "warranty_expiry": "2029-08-01",
            "allocatable_flag": "保留",
            "remark": "合同采购",
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 200, r.json()
    part = r.json()
    assert part["current_status"] == enums.STATUS_IN_STOCK
    assert part["allocatable_flag"] == "保留"
    assert part["source_type"] == "独立合同采购"


def test_manual_source_missing_fields_rejected(client):
    cast = demo_cast(client)
    loc_id = client.get("/api/storage-locations", headers=op_headers(1)).json()[0]["id"]
    r = client.post(
        "/api/parts/inbound",
        json={
            "model_id": _mem_model_id(client),
            "fixed_asset_no": "FA-CT-002",
            "source_type": "框招正偏移",
            "storage_location_id": loc_id,
            "serial_no": "SN-CT-002",
            "purchase_amount": 100.00,
            "allocatable_flag": "通用可调",
            "remark": "缺一堆字段",
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 400
    assert "必填" in r.json()["detail"]


def test_old_source_type_rejected(client):
    cast = demo_cast(client)
    r = client.post(
        "/api/parts/inbound",
        json={
            "model_id": _mem_model_id(client),
            "fixed_asset_no": "FA-OLD-001",
            "source_type": "单独合同",
            "serial_no": "SN-OLD-001",
            "purchase_amount": 100.00,
            "allocatable_flag": "通用可调",
            "remark": "旧枚举",
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 400
    assert "source_type" in r.json()["detail"]
