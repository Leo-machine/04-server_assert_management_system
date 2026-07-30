"""盘点发现层核心规则测试。不改动既有主线用例。"""

from datetime import date, timedelta

from app import enums
from app.services.stocktake import assert_stocktake_read_only_red_line
from tests.conftest import op_headers


def _stock_part(client):
    for p in client.get("/api/parts").json():
        if p["current_status"] == enums.STATUS_IN_STOCK:
            return p
    raise AssertionError("需要在库配件")


def _idle_server(client):
    for s in client.get("/api/servers").json():
        if s["run_status"] == enums.RUN_NOT_LIVE:
            return s
    raise AssertionError("需要未投运服务器")


def _locs(client):
    return client.get("/api/storage-locations").json()


def _users(client):
    return client.get("/api/users").json()


def _org(client):
    return client.get("/api/external-orgs").json()[0]


def _loan_part_via_mainline(client, part_id: int) -> None:
    users = _users(client)
    applicant, a1, a2, a3 = users[0], users[1], users[2], users[3]
    org = _org(client)
    approval_id = client.post(
        "/api/approvals/loan",
        json={
            "part_id": part_id,
            "dest_org_id": org["id"],
            "expected_return_date": str(date.today() + timedelta(days=7)),
            "approver_ids": [a1["id"], a2["id"], a3["id"]],
        },
        headers=op_headers(applicant["id"]),
    ).json()["id"]
    for level, approver in ((1, a1), (2, a2), (3, a3)):
        r = client.post(
            f"/api/approvals/{approval_id}/decide",
            json={"level": level, "approve": True},
            headers=op_headers(approver["id"]),
        )
        assert r.status_code == 200, r.text
    assert client.get(f"/api/parts/{part_id}").json()["current_status"] == enums.STATUS_LOANED


def test_snapshot_frozen_after_realtime_install(client):
    part = _stock_part(client)
    expected_kind = part["current_loc_kind"]
    expected_id = part["current_loc_id"]

    st = client.post(
        "/api/stocktakes",
        json={"scope_kind": "全盘"},
        headers=op_headers(1),
    ).json()
    item = next(i for i in st["items"] if i["part_id"] == part["id"])
    assert item["expected_loc_kind"] == expected_kind
    assert item["expected_loc_id"] == expected_id

    server = _idle_server(client)
    assert (
        client.post(
            f"/api/parts/{part['id']}/install",
            json={"server_id": server["id"]},
            headers=op_headers(1),
        ).status_code
        == 200
    )

    st2 = client.get(f"/api/stocktakes/{st['id']}").json()
    item2 = next(i for i in st2["items"] if i["part_id"] == part["id"])
    assert item2["expected_loc_kind"] == expected_kind
    assert item2["expected_loc_id"] == expected_id
    # 实时已变，但快照不变
    live = client.get(f"/api/parts/{part['id']}").json()
    assert live["current_loc_kind"] == enums.LOC_SERVER
    assert live["current_loc_id"] == server["id"]


def test_shortage_does_not_touch_part_or_movements(client):
    part = _stock_part(client)
    before_moves = client.get(f"/api/parts/{part['id']}/movements").json()
    before_status = part["current_status"]

    st = client.post(
        "/api/stocktakes",
        json={"scope_kind": "全盘"},
        headers=op_headers(1),
    ).json()

    r = client.post(
        f"/api/stocktakes/{st['id']}/check",
        json={"scanned_asset_no": part["fixed_asset_no"], "missing": True},
        headers=op_headers(1),
    )
    assert r.status_code == 200, r.text
    assert r.json()["result"] == enums.RESULT_SHORTAGE
    assert r.json()["discrepancy"]["status"] == enums.DISC_STATUS_HOLD

    after = client.get(f"/api/parts/{part['id']}").json()
    after_moves = client.get(f"/api/parts/{part['id']}/movements").json()
    assert after["current_status"] == before_status
    assert after["current_loc_kind"] == part["current_loc_kind"]
    assert after["current_loc_id"] == part["current_loc_id"]
    assert len(after_moves) == len(before_moves)


def test_shortage_hold_and_no_offset_api(client):
    part = _stock_part(client)
    st = client.post(
        "/api/stocktakes",
        json={"scope_kind": "全盘"},
        headers=op_headers(1),
    ).json()
    client.post(
        f"/api/stocktakes/{st['id']}/check",
        json={"scanned_asset_no": part["fixed_asset_no"], "missing": True},
        headers=op_headers(1),
    )
    discs = client.get(f"/api/stocktakes/{st['id']}/discrepancies").json()
    shortage = next(d for d in discs if d["discrepancy_type"] == enums.DISC_SHORTAGE)
    assert shortage["status"] == enums.DISC_STATUS_HOLD

    # 不存在对冲 / 自动已处置路径
    for path in (
        f"/api/stocktakes/{st['id']}/offset",
        f"/api/stocktakes/{st['id']}/discrepancies/{shortage['id']}/resolve",
        f"/api/stocktakes/{st['id']}/discrepancies/{shortage['id']}/offset",
    ):
        assert client.post(path, headers=op_headers(1)).status_code in (404, 405)


def test_external_confirm_via_mainline_loan(client):
    part = _stock_part(client)
    _loan_part_via_mainline(client, part["id"])

    st = client.post(
        "/api/stocktakes",
        json={"scope_kind": "全盘"},
        headers=op_headers(1),
    ).json()
    item = next(i for i in st["items"] if i["part_id"] == part["id"])
    assert item["expected_loc_kind"] == enums.LOC_EXTERNAL
    assert item["result"] == enums.RESULT_PENDING
    assert item["requires_external_confirm"] is True

    # 未函证不得为相符；现场 check 应拒绝
    bad = client.post(
        f"/api/stocktakes/{st['id']}/check",
        json={
            "scanned_asset_no": part["fixed_asset_no"],
            "actual_loc_kind": enums.LOC_EXTERNAL,
            "actual_loc_id": item["expected_loc_id"],
        },
        headers=op_headers(1),
    )
    assert bad.status_code == 400

    missing = client.post(
        f"/api/stocktakes/{st['id']}/confirm-external",
        json={
            "item_id": item["id"],
            "present": False,
            "feedback_source": "兄弟单位信息中心-周工",
        },
        headers=op_headers(1),
    )
    assert missing.status_code == 200, missing.text
    assert missing.json()["result"] == enums.RESULT_SHORTAGE
    assert missing.json()["discrepancy"]["status"] == enums.DISC_STATUS_HOLD


def test_complete_requires_no_pending(client):
    part = _stock_part(client)
    locs = _locs(client)
    st = client.post(
        "/api/stocktakes",
        json={"scope_kind": "全盘"},
        headers=op_headers(1),
    ).json()

    early = client.post(
        f"/api/stocktakes/{st['id']}/complete",
        headers=op_headers(1),
    )
    assert early.status_code == 400
    assert "待复核" in early.json()["detail"]

    # 盘完全部账内明细（外单位若无则现场件）
    for item in st["items"]:
        if item["expected_loc_kind"] == enums.LOC_EXTERNAL:
            client.post(
                f"/api/stocktakes/{st['id']}/confirm-external",
                json={
                    "item_id": item["id"],
                    "present": True,
                    "feedback_source": "函证确认在",
                },
                headers=op_headers(1),
            )
        else:
            client.post(
                f"/api/stocktakes/{st['id']}/check",
                json={
                    "scanned_asset_no": item["fixed_asset_no"],
                    "actual_loc_kind": item["expected_loc_kind"],
                    "actual_loc_id": item["expected_loc_id"],
                },
                headers=op_headers(1),
            )

    # 再造一条盘盈并结案
    client.post(
        f"/api/stocktakes/{st['id']}/check",
        json={
            "scanned_asset_no": "FA-SURPLUS-ONLY-001",
            "actual_loc_kind": enums.LOC_STORAGE,
            "actual_loc_id": locs[0]["id"],
        },
        headers=op_headers(1),
    )

    before_part = client.get(f"/api/parts/{part['id']}").json()
    before_moves = len(client.get(f"/api/parts/{part['id']}/movements").json())
    done = client.post(
        f"/api/stocktakes/{st['id']}/complete",
        headers=op_headers(1),
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == enums.STOCKTAKE_COMPLETED
    after_part = client.get(f"/api/parts/{part['id']}").json()
    assert after_part["current_status"] == before_part["current_status"]
    assert len(client.get(f"/api/parts/{part['id']}/movements").json()) == before_moves


def test_check_three_branches_match_misplace_surplus(client):
    locs = _locs(client)
    parts = [
        p
        for p in client.get("/api/parts").json()
        if p["current_status"] == enums.STATUS_IN_STOCK
    ]
    assert len(parts) >= 2
    p_match, p_mis = parts[0], parts[1]

    st = client.post(
        "/api/stocktakes",
        json={"scope_kind": "全盘"},
        headers=op_headers(1),
    ).json()

    # 分支1 相符
    r1 = client.post(
        f"/api/stocktakes/{st['id']}/check",
        json={
            "scanned_asset_no": p_match["fixed_asset_no"],
            "actual_loc_kind": p_match["current_loc_kind"],
            "actual_loc_id": p_match["current_loc_id"],
        },
        headers=op_headers(1),
    )
    assert r1.status_code == 200
    assert r1.json()["result"] == enums.RESULT_MATCH

    # 分支1 错位
    other_loc = next(l for l in locs if l["id"] != p_mis["current_loc_id"])
    r2 = client.post(
        f"/api/stocktakes/{st['id']}/check",
        json={
            "scanned_asset_no": p_mis["fixed_asset_no"],
            "actual_loc_kind": enums.LOC_STORAGE,
            "actual_loc_id": other_loc["id"],
        },
        headers=op_headers(1),
    )
    assert r2.status_code == 200
    assert r2.json()["result"] == enums.RESULT_MISPLACE

    # 分支3 查全表盘盈
    r3 = client.post(
        f"/api/stocktakes/{st['id']}/check",
        json={
            "scanned_asset_no": "FA-NOT-IN-SYSTEM-999",
            "actual_loc_kind": enums.LOC_STORAGE,
            "actual_loc_id": locs[0]["id"],
        },
        headers=op_headers(1),
    )
    assert r3.status_code == 200
    assert r3.json()["result"] == enums.RESULT_SURPLUS
    assert r3.json()["part_id"] is None
    assert r3.json()["scanned_asset_no"] == "FA-NOT-IN-SYSTEM-999"


def test_stocktake_read_only_red_line_static():
    assert_stocktake_read_only_red_line()
