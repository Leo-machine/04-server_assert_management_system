"""第一波功能测试：报废/调拨审批、损坏态、撤回、查重统一、bug 修复回归。"""

from datetime import date, timedelta

from app import enums
from tests.conftest import demo_cast, op_headers


# ---------- 辅助 ----------

def _users(client):
    return client.get("/api/users", headers=op_headers(1)).json()


def _locs(client):
    return client.get("/api/storage-locations", headers=op_headers(1)).json()


def _org(client):
    return client.get("/api/external-orgs", headers=op_headers(1)).json()[0]


def _parts(client):
    return client.get("/api/parts", headers=op_headers(1)).json()


def _stock_part_ids(client) -> list[int]:
    return [
        p["id"]
        for p in _parts(client)
        if p["current_status"] == enums.STATUS_IN_STOCK
    ]


def _approve_full(client, approval_id: int, approver_ids: list[int]):
    for level, uid in enumerate(approver_ids, start=1):
        r = client.post(
            f"/api/approvals/{approval_id}/decide",
            json={"level": level, "approve": True},
            headers=op_headers(uid),
        )
        assert r.status_code == 200, r.json()
    return r.json()


def _last_movement(client, part_id: int) -> dict:
    moves = client.get(f"/api/parts/{part_id}/movements", headers=op_headers(1)).json()
    assert moves, "应有履历"
    return moves[-1]


def _inbound(client, *, sensitivity=None) -> int:
    models = client.get("/api/part-models", headers=op_headers(1)).json()
    loc_id = _locs(client)[0]["id"]
    r = client.post(
        "/api/parts/inbound",
        json={
            "model_id": models[0]["id"],
            "fixed_asset_no": f"FA-W1-{sensitivity or 'NORMAL'}-001",
            "storage_location_id": loc_id,
            "source_type": "独立合同采购",
            "responsible_group": "基础组",
            "serial_no": f"SN-W1-{sensitivity or 'NORMAL'}-001",
            "contract_no": "HT-TEST-001",
            "purchase_amount": 1000.00,
            "purchase_date": "2026-01-01",
            "sensitivity": sensitivity or "无",
            "supplier": "通用配件供应商",
            "project": "测试项目",
            "owner_unit": "本单位信息中心",
            "warranty_expiry": "2029-01-01",
            "allocatable_flag": "通用可调",
            "remark": "测试入库",
        },
        headers=op_headers(1),
    )
    assert r.status_code == 200, r.json()
    return r.json()["id"]


# ---------- 报废 ----------

def test_scrap_from_stock_full_flow(client):
    part_id = _stock_part_ids(client)[0]
    cast = demo_cast(client)
    users = cast["users"]
    approvers = cast["approver_ids"]

    r = client.post(
        "/api/approvals/scrap",
        json={
            "part_id": part_id,
            "reason_code": enums.REASON_SCRAP_DESTROY,
            "approver_ids": approvers,
            "remark": "例行报废",
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 200, r.json()
    ap = r.json()
    assert ap["action_type"] == enums.ACTION_SCRAP
    assert ap["overall_status"] == enums.APPROVAL_PENDING
    assert ap["reason_code"] == enums.REASON_SCRAP_DESTROY
    assert ap["expected_return_date"] is None
    assert ap["dest_org_id"] is None

    final = _approve_full(client, ap["id"], approvers)
    assert final["overall_status"] == enums.APPROVAL_APPROVED

    part = client.get(f"/api/parts/{part_id}", headers=op_headers(1)).json()
    assert part["current_status"] == enums.STATUS_SCRAPPED
    assert part["current_loc_kind"] == enums.LOC_NONE
    assert part["current_loc_id"] is None

    mv = _last_movement(client, part_id)
    assert mv["event_type"] == enums.EVENT_SCRAP
    assert mv["status_to"] == enums.STATUS_SCRAPPED
    assert mv["reason_code"] == enums.REASON_SCRAP_DESTROY
    assert mv["approval_id"] == ap["id"]
    assert mv["loc_to_kind"] == enums.LOC_NONE

    # 终态：任何后续操作被拦截
    loc_id = _locs(client)[0]["id"]
    r2 = client.post(
        f"/api/parts/{part_id}/install",
        json={"server_id": 2},
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r2.status_code == 400
    r3 = client.post(
        "/api/approvals/scrap",
        json={
            "part_id": part_id,
            "reason_code": enums.REASON_SCRAP_DESTROY,
            "approver_ids": approvers,
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r3.status_code == 400


def test_scrap_from_damaged(client):
    part_id = _stock_part_ids(client)[0]
    cast = demo_cast(client)
    users = cast["users"]
    approvers = cast["approver_ids"]

    r = client.post(
        f"/api/parts/{part_id}/damage",
        json={"remark": "库内发现金手指氧化"},
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 200
    assert r.json()["current_status"] == enums.STATUS_DAMAGED

    r = client.post(
        "/api/approvals/scrap",
        json={
            "part_id": part_id,
            "reason_code": enums.REASON_SCRAP_FACTORY,
            "approver_ids": approvers,
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 200, r.json()
    final = _approve_full(client, r.json()["id"], approvers)
    assert final["overall_status"] == enums.APPROVAL_APPROVED

    part = client.get(f"/api/parts/{part_id}", headers=op_headers(1)).json()
    assert part["current_status"] == enums.STATUS_SCRAPPED
    mv = _last_movement(client, part_id)
    assert mv["event_type"] == enums.EVENT_SCRAP
    assert mv["status_from"] == enums.STATUS_DAMAGED
    assert mv["reason_code"] == enums.REASON_SCRAP_FACTORY


def test_scrap_rejected_writes_no_movement(client):
    part_id = _stock_part_ids(client)[0]
    cast = demo_cast(client)
    users = cast["users"]
    approvers = cast["approver_ids"]

    ap = client.post(
        "/api/approvals/scrap",
        json={
            "part_id": part_id,
            "reason_code": enums.REASON_SCRAP_DESTROY,
            "approver_ids": approvers,
        },
        headers=op_headers(cast["applicant"]["id"]),
    ).json()
    r = client.post(
        f"/api/approvals/{ap['id']}/decide",
        json={"level": 1, "approve": False, "opinion": "尚有利用价值"},
        headers=op_headers(approvers[0]),
    )
    assert r.status_code == 200
    assert r.json()["overall_status"] == enums.APPROVAL_REJECTED

    part = client.get(f"/api/parts/{part_id}", headers=op_headers(1)).json()
    assert part["current_status"] == enums.STATUS_IN_STOCK
    moves = client.get(f"/api/parts/{part_id}/movements", headers=op_headers(1)).json()
    assert all(m["event_type"] != enums.EVENT_SCRAP for m in moves)


def test_scrap_voided_when_status_changed_before_final(client, db_session):
    from app.models import Part

    part_id = _stock_part_ids(client)[0]
    cast = demo_cast(client)
    approvers = cast["approver_ids"]

    ap = client.post(
        "/api/approvals/scrap",
        json={
            "part_id": part_id,
            "reason_code": enums.REASON_SCRAP_DESTROY,
            "approver_ids": approvers,
        },
        headers=op_headers(cast["applicant"]["id"]),
    ).json()
    for level, uid in ((1, approvers[0]), (2, approvers[1])):
        client.post(
            f"/api/approvals/{ap['id']}/decide",
            json={"level": level, "approve": True},
            headers=op_headers(uid),
        )

    # 审批中禁止装机；竞态用 DB 直改模拟状态漂移
    r = client.post(
        f"/api/parts/{part_id}/install",
        json={"server_id": 2},
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 400
    assert "审批中" in r.json()["detail"]

    part_row = db_session.get(Part, part_id)
    part_row.current_status = enums.STATUS_IN_USE
    part_row.current_loc_kind = enums.LOC_SERVER
    part_row.current_loc_id = 2
    db_session.commit()

    final = client.post(
        f"/api/approvals/{ap['id']}/decide",
        json={"level": 3, "approve": True},
        headers=op_headers(approvers[2]),
    )
    assert final.status_code == 400
    assert "审批已作废" in final.json()["detail"]

    part = client.get(f"/api/parts/{part_id}", headers=op_headers(1)).json()
    assert part["current_status"] == enums.STATUS_IN_USE
    moves = client.get(f"/api/parts/{part_id}/movements", headers=op_headers(1)).json()
    assert all(m["event_type"] != enums.EVENT_SCRAP for m in moves)
    ap_after = client.get(f"/api/approvals/{ap['id']}", headers=op_headers(1)).json()
    assert ap_after["overall_status"] == enums.APPROVAL_REJECTED
    assert "系统作废" in ap_after["remark"]


def _inbound_gpu(client) -> int:
    """入库一个在库算力卡（报废影像证据按类型强制的测试件）。"""
    models = client.get("/api/part-models", headers=op_headers(1)).json()
    gpu = next(m for m in models if m["category"] == "算力卡")
    locs = client.get("/api/storage-locations", headers=op_headers(1)).json()
    loc = next(
        l for l in locs
        if not l.get("allowed_categories") or "算力卡" in l["allowed_categories"]
    )
    cast = demo_cast(client)
    r = client.post(
        "/api/parts/inbound",
        json={
            "model_id": gpu["id"],
            "fixed_asset_no": "FA-W1-GPU-001",
            "storage_location_id": loc["id"],
            "source_type": "独立合同采购",
            "responsible_group": "基础组",
            "serial_no": "SN-W1-GPU-001",
            "contract_no": "HT-W1-001",
            "purchase_amount": 50000,
            "purchase_date": "2026-07-01",
            "supplier": "通用配件供应商",
            "project": "测试项目",
            "owner_unit": "本单位信息中心",
            "warranty_expiry": "2028-07-01",
            "allocatable_flag": "通用可调",
            "remark": "测试",
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 200, r.json()
    return r.json()["id"]


def test_scrap_gpu_requires_attachment(client):
    """算力卡类高值件报废：无影像证据拦截，有证据放行（按配件类型判断）。"""
    part_id = _inbound_gpu(client)
    cast = demo_cast(client)
    approvers = cast["approver_ids"]

    r = client.post(
        "/api/approvals/scrap",
        json={
            "part_id": part_id,
            "reason_code": enums.REASON_SCRAP_FACTORY,
            "approver_ids": approvers,
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 400
    assert "影像证据" in r.json()["detail"]

    r2 = client.post(
        "/api/approvals/scrap",
        json={
            "part_id": part_id,
            "reason_code": enums.REASON_SCRAP_FACTORY,
            "approver_ids": approvers,
            "attachment_ref": "WO-2026-0731-照片.zip",
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r2.status_code == 200
    assert r2.json()["attachment_ref"] == "WO-2026-0731-照片.zip"


def test_scrap_non_gpu_no_attachment(client):
    """非算力卡类型（如内存）报废不得强制影像证据。"""
    part_id = _inbound(client)
    cast = demo_cast(client)
    r = client.post(
        "/api/approvals/scrap",
        json={
            "part_id": part_id,
            "reason_code": enums.REASON_SCRAP_DESTROY,
            "approver_ids": cast["approver_ids"],
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 200


def test_inbound_rejects_location_category_mismatch(client):
    """后端必须校验库位 allowed_categories，不能只靠前端过滤。"""
    models = client.get("/api/part-models", headers=op_headers(1)).json()
    mem = next(m for m in models if m["category"] == "内存")
    locs = client.get("/api/storage-locations", headers=op_headers(1)).json()
    # seed: Rack-D-12 仅允许 GPU卡/算力卡
    restricted = next(
        (l for l in locs if l.get("allowed_categories") and "内存" not in (l.get("allowed_categories") or [])),
        None,
    )
    if restricted is None:
        # 若当前库位列表无限制位，先创建一个
        created = client.post(
            "/api/storage-locations",
            json={
                "warehouse": "限制库",
                "slot": "GPU-ONLY",
                "location_type": "库房货架",
                "allowed_categories": ["算力卡"],
            },
            headers=op_headers(1),
        )
        assert created.status_code == 200, created.text
        restricted = created.json()

    r = client.post(
        "/api/parts/inbound",
        json={
            "model_id": mem["id"],
            "fixed_asset_no": "FA-LOC-MISMATCH-1",
            "storage_location_id": restricted["id"],
            "source_type": "独立合同采购",
            "responsible_group": "基础组",
            "serial_no": "SN-LOC-MISMATCH-1",
            "contract_no": "HT-LOC-1",
            "purchase_amount": 100.0,
            "purchase_date": "2026-01-01",
            "sensitivity": "无",
            "supplier": "通用配件供应商",
            "project": "库位校验",
            "owner_unit": "本单位信息中心",
            "warranty_expiry": "2029-01-01",
            "allocatable_flag": "通用可调",
            "remark": "应被拒绝",
        },
        headers=op_headers(1),
    )
    assert r.status_code == 400
    assert "仅允许" in r.json()["detail"]


def test_scrap_invalid_reason_code(client):
    part_id = _stock_part_ids(client)[0]
    cast = demo_cast(client)
    users = cast["users"]
    r = client.post(
        "/api/approvals/scrap",
        json={
            "part_id": part_id,
            "reason_code": "随便扔了",
            "approver_ids": cast["approver_ids"],
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 400
    assert "报废缘由" in r.json()["detail"]


# ---------- 调拨 ----------

def test_transfer_full_flow(client):
    part_id = _stock_part_ids(client)[0]
    cast = demo_cast(client)
    org = _org(client)
    approvers = cast["approver_ids"]

    r = client.post(
        "/api/approvals/transfer",
        json={
            "part_id": part_id,
            "dest_org_id": org["id"],
            "approver_ids": approvers,
            "reason_code": "集团内划转",
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 200, r.json()
    ap = r.json()
    assert ap["action_type"] == enums.ACTION_TRANSFER
    assert ap["dest_org_id"] == org["id"]

    final = _approve_full(client, ap["id"], approvers)
    assert final["overall_status"] == enums.APPROVAL_APPROVED

    part = client.get(f"/api/parts/{part_id}", headers=op_headers(1)).json()
    assert part["current_status"] == enums.STATUS_TRANSFERRED
    assert part["current_loc_kind"] == enums.LOC_EXTERNAL
    assert part["current_loc_id"] == org["id"]

    mv = _last_movement(client, part_id)
    assert mv["event_type"] == enums.EVENT_TRANSFER
    assert mv["status_to"] == enums.STATUS_TRANSFERRED
    assert mv["loc_to_kind"] == enums.LOC_EXTERNAL
    assert mv["reason_code"] == "集团内划转"

    # 终态不可再流转
    r2 = client.post(
        f"/api/parts/{part_id}/install",
        json={"server_id": 2},
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r2.status_code == 400


def test_transfer_from_damaged_blocked(client):
    part_id = _stock_part_ids(client)[0]
    cast = demo_cast(client)
    users = cast["users"]
    client.post(
        f"/api/parts/{part_id}/damage",
        json={"remark": "损坏"},
        headers=op_headers(cast["applicant"]["id"]),
    )
    r = client.post(
        "/api/approvals/transfer",
        json={
            "part_id": part_id,
            "dest_org_id": _org(client)["id"],
            "approver_ids": cast["approver_ids"],
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 400
    assert "非法起始状态" in r.json()["detail"]


# ---------- 损坏态 ----------

def test_uninstall_damaged_goes_to_damaged(client):
    parts = _parts(client)
    servers = {s["id"]: s for s in client.get("/api/servers", headers=op_headers(1)).json()}
    idle = next(
        p
        for p in parts
        if p["current_status"] == enums.STATUS_IN_USE
        and p["current_loc_kind"] == enums.LOC_SERVER
        and servers[p["current_loc_id"]]["run_status"] == enums.RUN_NOT_LIVE
    )
    loc_id = _locs(client)[0]["id"]
    r = client.post(
        f"/api/parts/{idle['id']}/uninstall",
        json={"storage_location_id": loc_id, "damaged": True, "remark": "点不亮"},
        headers=op_headers(1),
    )
    assert r.status_code == 200, r.json()
    assert r.json()["current_status"] == enums.STATUS_DAMAGED
    assert r.json()["current_loc_kind"] == enums.LOC_STORAGE
    mv = _last_movement(client, idle["id"])
    assert mv["event_type"] == enums.EVENT_UNINSTALL
    assert mv["status_to"] == enums.STATUS_DAMAGED


def test_live_server_blocks_damaged_uninstall(client):
    parts = _parts(client)
    servers = {s["id"]: s for s in client.get("/api/servers", headers=op_headers(1)).json()}
    live = next(
        p
        for p in parts
        if p["current_status"] == enums.STATUS_IN_USE
        and servers[p["current_loc_id"]]["run_status"] == enums.RUN_LIVE
    )
    r = client.post(
        f"/api/parts/{live['id']}/uninstall",
        json={"storage_location_id": _locs(client)[0]["id"], "damaged": True},
        headers=op_headers(1),
    )
    assert r.status_code == 400
    assert "投运" in r.json()["detail"]


def test_report_damage_requires_remark(client):
    part_id = _stock_part_ids(client)[0]
    r = client.post(
        f"/api/parts/{part_id}/damage",
        json={"remark": "  "},
        headers=op_headers(1),
    )
    assert r.status_code == 400


def test_damaged_part_blocked_from_install_and_loan(client):
    part_id = _stock_part_ids(client)[0]
    cast = demo_cast(client)
    users = cast["users"]
    client.post(
        f"/api/parts/{part_id}/damage",
        json={"remark": "损坏"},
        headers=op_headers(cast["applicant"]["id"]),
    )
    r = client.post(
        f"/api/parts/{part_id}/install",
        json={"server_id": 2},
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 400
    r2 = client.post(
        "/api/approvals/loan",
        json={
            "part_id": part_id,
            "dest_org_id": _org(client)["id"],
            "expected_return_date": str(date.today() + timedelta(days=7)),
            "approver_ids": cast["approver_ids"],
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r2.status_code == 400


# ---------- 撤回 ----------

def test_withdraw_by_applicant_and_reapply(client):
    part_id = _stock_part_ids(client)[0]
    cast = demo_cast(client)
    users = cast["users"]
    approvers = cast["approver_ids"]

    ap = client.post(
        "/api/approvals/scrap",
        json={
            "part_id": part_id,
            "reason_code": enums.REASON_SCRAP_DESTROY,
            "approver_ids": approvers,
        },
        headers=op_headers(cast["applicant"]["id"]),
    ).json()

    r = client.post(
        f"/api/approvals/{ap['id']}/withdraw",
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 200
    assert r.json()["overall_status"] == enums.APPROVAL_WITHDRAWN

    # 撤回不写履历
    moves = client.get(f"/api/parts/{part_id}/movements", headers=op_headers(1)).json()
    assert all(m["event_type"] != enums.EVENT_SCRAP for m in moves)

    # 撤回后可重新发起
    r2 = client.post(
        "/api/approvals/scrap",
        json={
            "part_id": part_id,
            "reason_code": enums.REASON_SCRAP_DESTROY,
            "approver_ids": approvers,
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r2.status_code == 200


def test_withdraw_by_non_applicant_blocked(client):
    part_id = _stock_part_ids(client)[0]
    cast = demo_cast(client)
    users = cast["users"]
    ap = client.post(
        "/api/approvals/scrap",
        json={
            "part_id": part_id,
            "reason_code": enums.REASON_SCRAP_DESTROY,
            "approver_ids": cast["approver_ids"],
        },
        headers=op_headers(cast["applicant"]["id"]),
    ).json()
    r = client.post(
        f"/api/approvals/{ap['id']}/withdraw",
        headers=op_headers(cast["a1"]["id"]),
    )
    assert r.status_code == 400
    assert "申请人" in r.json()["detail"]


def test_withdraw_finished_approval_blocked(client):
    part_id = _stock_part_ids(client)[0]
    cast = demo_cast(client)
    users = cast["users"]
    approvers = cast["approver_ids"]
    ap = client.post(
        "/api/approvals/scrap",
        json={
            "part_id": part_id,
            "reason_code": enums.REASON_SCRAP_DESTROY,
            "approver_ids": approvers,
        },
        headers=op_headers(cast["applicant"]["id"]),
    ).json()
    _approve_full(client, ap["id"], approvers)
    r = client.post(
        f"/api/approvals/{ap['id']}/withdraw",
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 400
    assert "不可撤回" in r.json()["detail"]


# ---------- in-flight 查重统一（不限类型） ----------

def test_inflight_blocks_any_action_type(client):
    part_id = _stock_part_ids(client)[0]
    cast = demo_cast(client)
    users = cast["users"]
    approvers = cast["approver_ids"]
    org = _org(client)

    loan = client.post(
        "/api/approvals/loan",
        json={
            "part_id": part_id,
            "dest_org_id": org["id"],
            "expected_return_date": str(date.today() + timedelta(days=7)),
            "approver_ids": approvers,
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert loan.status_code == 200

    scrap = client.post(
        "/api/approvals/scrap",
        json={
            "part_id": part_id,
            "reason_code": enums.REASON_SCRAP_DESTROY,
            "approver_ids": approvers,
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert scrap.status_code == 400
    assert "审批中" in scrap.json()["detail"]

    transfer = client.post(
        "/api/approvals/transfer",
        json={
            "part_id": part_id,
            "dest_org_id": org["id"],
            "approver_ids": approvers,
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert transfer.status_code == 400


# ---------- bug 修复回归 ----------

def test_brand_rename_cascades_and_delete_guard(client):
    r = client.post(
        "/api/brands", json={"name": "测试品牌X"}, headers=op_headers(1)
    )
    brand_id = r.json()["id"]
    client.post(
        "/api/part-models",
        json={
            "category": "内存",
            "model_name": "测试品牌X 16G DDR4",
            "brand": "测试品牌X",
            "spec": {"容量GB": 16, "内存类型": "DDR4"},
        },
        headers=op_headers(1),
    )

    r2 = client.put(
        f"/api/brands/{brand_id}", json={"name": "测试品牌Y"}, headers=op_headers(1)
    )
    assert r2.status_code == 200
    models = client.get("/api/part-models?category=内存", headers=op_headers(1)).json()
    renamed = [m for m in models if m["model_name"] == "测试品牌X 16G DDR4"]
    assert renamed and renamed[0]["brand"] == "测试品牌Y"

    r3 = client.delete(f"/api/brands/{brand_id}", headers=op_headers(1))
    assert r3.status_code == 400
    assert "引用" in r3.json()["detail"]


def test_surplus_rescan_is_idempotent(client):
    st = client.post("/api/stocktakes", json={}, headers=op_headers(1)).json()
    for _ in range(2):
        r = client.post(
            f"/api/stocktakes/{st['id']}/check",
            json={
                "scanned_asset_no": "FA-NOPE-0001",
                "actual_loc_kind": "库位",
                "actual_loc_id": _locs(client)[0]["id"],
            },
            headers=op_headers(1),
        )
        assert r.status_code == 200
    st_after = client.get(f"/api/stocktakes/{st['id']}", headers=op_headers(1)).json()
    surplus = [i for i in st_after["items"] if i["result"] == enums.RESULT_SURPLUS]
    assert len(surplus) == 1


def test_loan_past_return_date_blocked(client):
    part_id = _stock_part_ids(client)[0]
    cast = demo_cast(client)
    users = cast["users"]
    r = client.post(
        "/api/approvals/loan",
        json={
            "part_id": part_id,
            "dest_org_id": _org(client)["id"],
            "expected_return_date": str(date.today() - timedelta(days=1)),
            "approver_ids": cast["approver_ids"],
        },
        headers=op_headers(cast["applicant"]["id"]),
    )
    assert r.status_code == 400
    assert "归还日" in r.json()["detail"]


def test_stocktake_check_validates_actual_loc(client):
    st = client.post("/api/stocktakes", json={}, headers=op_headers(1)).json()
    stock_part = next(
        p for p in st["items"] if p["expected_loc_kind"] == enums.LOC_STORAGE
    )
    asset_no = stock_part["fixed_asset_no"]

    r = client.post(
        f"/api/stocktakes/{st['id']}/check",
        json={"scanned_asset_no": asset_no, "actual_loc_kind": "火星", "actual_loc_id": 1},
        headers=op_headers(1),
    )
    assert r.status_code == 400
    assert "非法位置种类" in r.json()["detail"]

    r2 = client.post(
        f"/api/stocktakes/{st['id']}/check",
        json={
            "scanned_asset_no": asset_no,
            "actual_loc_kind": "库位",
            "actual_loc_id": 99999,
        },
        headers=op_headers(1),
    )
    assert r2.status_code == 400
    assert "位置不存在" in r2.json()["detail"]
