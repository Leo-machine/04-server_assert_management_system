"""角色矩阵：领导全权；主业=外委（无审批）；供应商无配件列表/可调余量。"""

from tests.conftest import demo_cast, op_headers


def _by_role(cast, role):
    return next(u for u in cast["users"] if u["role"] == role)


def test_supplier_cannot_view_parts_or_inventory(client):
    cast = demo_cast(client)
    supplier = _by_role(cast, "设备供应商")
    h = op_headers(supplier["id"])
    assert client.get("/api/parts", headers=h).status_code == 403
    assert client.get("/api/inventory/allocatable-summary", headers=h).status_code == 403


def test_ops_and_maintenance_can_view_parts(client):
    cast = demo_cast(client)
    for role in ("主业运维", "外委运维", "领导"):
        u = _by_role(cast, role)
        r = client.get("/api/parts", headers=op_headers(u["id"]))
        assert r.status_code == 200, role


def test_operations_cannot_decide_approval(client):
    cast = demo_cast(client)
    ops = _by_role(cast, "主业运维")
    # 即使伪造调用 decide，角色门禁应 403
    r = client.post(
        "/api/approvals/1/decide",
        json={"level": 1, "approve": True, "opinion": "同意"},
        headers=op_headers(ops["id"]),
    )
    assert r.status_code in (403, 400, 404)


def test_maintenance_can_create_stocktake_and_loan(client):
    cast = demo_cast(client)
    maint = _by_role(cast, "外委运维")
    h = op_headers(maint["id"])
    r = client.post("/api/stocktakes", json={"scope_kind": "全盘"}, headers=h)
    assert r.status_code == 200, r.text

    parts = client.get("/api/parts", headers=h).json()
    part = next(p for p in parts if p["current_status"] == "在库")
    orgs = client.get("/api/external-orgs", headers=h).json()
    r2 = client.post(
        "/api/approvals/loan",
        json={
            "part_id": part["id"],
            "dest_org_id": orgs[0]["id"],
            "expected_return_date": "2026-12-31",
            "approver_ids": cast["approver_ids"],
        },
        headers=h,
    )
    assert r2.status_code == 200, r2.text


def test_only_leader_can_decide(client):
    cast = demo_cast(client)
    leader = cast["a1"]
    assert leader["role"] == "领导"
    # 创建审批单
    ops = _by_role(cast, "主业运维")
    parts = client.get("/api/parts", headers=op_headers(ops["id"])).json()
    part = next(p for p in parts if p["current_status"] == "在库")
    orgs = client.get("/api/external-orgs", headers=op_headers(ops["id"])).json()
    ap = client.post(
        "/api/approvals/loan",
        json={
            "part_id": part["id"],
            "dest_org_id": orgs[0]["id"],
            "expected_return_date": "2026-12-31",
            "approver_ids": cast["approver_ids"],
        },
        headers=op_headers(ops["id"]),
    ).json()
    r = client.post(
        f"/api/approvals/{ap['id']}/decide",
        json={"level": 1, "approve": True, "opinion": "同意"},
        headers=op_headers(leader["id"]),
    )
    assert r.status_code == 200, r.text
