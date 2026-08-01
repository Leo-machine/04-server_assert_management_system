"""本主线防流失核心规则测试。"""

from datetime import date, timedelta

from sqlalchemy import inspect

from app import enums
from app.seed import assert_no_movement_mutation_api
from tests.conftest import op_headers


def _stock_part_id(client) -> int:
    parts = client.get("/api/parts").json()
    for p in parts:
        if p["current_status"] == enums.STATUS_IN_STOCK:
            return p["id"]
    raise AssertionError("种子中应有在库配件")


def _live_server_part(client) -> tuple:
    servers = {s["id"]: s for s in client.get("/api/servers").json()}
    parts = client.get("/api/parts").json()
    for p in parts:
        if (
            p["current_status"] == enums.STATUS_IN_USE
            and p["current_loc_kind"] == enums.LOC_SERVER
            and servers.get(p["current_loc_id"], {}).get("run_status") == enums.RUN_LIVE
        ):
            return p["id"], p["current_loc_id"]
    raise AssertionError("种子中应有投运服务器上的在用件")


def _idle_server(client) -> int:
    for s in client.get("/api/servers").json():
        if s["run_status"] == enums.RUN_NOT_LIVE:
            return s["id"]
    raise AssertionError("种子中应有未投运服务器")


def _users(client):
    return client.get("/api/users").json()


def _locs(client):
    return client.get("/api/storage-locations").json()


def _org(client):
    return client.get("/api/external-orgs").json()[0]


def test_live_server_blocks_uninstall(client):
    part_id, server_id = _live_server_part(client)
    loc_id = _locs(client)[0]["id"]
    r = client.post(
        f"/api/parts/{part_id}/uninstall",
        json={"storage_location_id": loc_id},
        headers=op_headers(1),
    )
    assert r.status_code == 400
    assert "投运" in r.json()["detail"]

    patch = client.patch(
        f"/api/servers/{server_id}/run-status",
        json={"run_status": enums.RUN_NOT_LIVE},
    )
    assert patch.status_code == 200
    r2 = client.post(
        f"/api/parts/{part_id}/uninstall",
        json={"storage_location_id": loc_id},
        headers=op_headers(1),
    )
    assert r2.status_code == 200
    assert r2.json()["current_status"] == enums.STATUS_IN_STOCK


def test_loan_requires_full_approval(client):
    part_id = _stock_part_id(client)
    users = _users(client)
    applicant, a1, a2, a3 = users[0], users[1], users[2], users[3]
    org = _org(client)

    create = client.post(
        "/api/approvals/loan",
        json={
            "part_id": part_id,
            "dest_org_id": org["id"],
            "expected_return_date": str(date.today() + timedelta(days=7)),
            "approver_ids": [a1["id"], a2["id"], a3["id"]],
        },
        headers=op_headers(applicant["id"]),
    )
    assert create.status_code == 200
    approval_id = create.json()["id"]

    r1 = client.post(
        f"/api/approvals/{approval_id}/decide",
        json={"level": 1, "approve": True},
        headers=op_headers(a1["id"]),
    )
    assert r1.status_code == 200
    part = client.get(f"/api/parts/{part_id}").json()
    assert part["current_status"] == enums.STATUS_IN_STOCK
    moves = client.get(f"/api/parts/{part_id}/movements").json()
    assert all(m["event_type"] != enums.EVENT_LOAN for m in moves)


def test_stepwise_and_veto(client):
    part_id = _stock_part_id(client)
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

    early = client.post(
        f"/api/approvals/{approval_id}/decide",
        json={"level": 2, "approve": True},
        headers=op_headers(a2["id"]),
    )
    assert early.status_code == 400

    client.post(
        f"/api/approvals/{approval_id}/decide",
        json={"level": 1, "approve": True},
        headers=op_headers(a1["id"]),
    )
    reject = client.post(
        f"/api/approvals/{approval_id}/decide",
        json={"level": 2, "approve": False, "opinion": "不同意"},
        headers=op_headers(a2["id"]),
    )
    assert reject.status_code == 200
    assert reject.json()["overall_status"] == enums.APPROVAL_REJECTED
    part = client.get(f"/api/parts/{part_id}").json()
    assert part["current_status"] == enums.STATUS_IN_STOCK


def test_approval_recusal(client):
    part_id = _stock_part_id(client)
    users = _users(client)
    applicant = users[0]
    org = _org(client)

    r = client.post(
        "/api/approvals/loan",
        json={
            "part_id": part_id,
            "dest_org_id": org["id"],
            "expected_return_date": str(date.today() + timedelta(days=7)),
            "approver_ids": [applicant["id"], users[1]["id"], users[2]["id"]],
        },
        headers=op_headers(applicant["id"]),
    )
    assert r.status_code == 400
    assert "回避" in r.json()["detail"]

    r2 = client.post(
        "/api/approvals/loan",
        json={
            "part_id": part_id,
            "dest_org_id": org["id"],
            "expected_return_date": str(date.today() + timedelta(days=7)),
            "approver_ids": [users[1]["id"], users[1]["id"], users[2]["id"]],
        },
        headers=op_headers(applicant["id"]),
    )
    assert r2.status_code == 400
    assert "互不相同" in r2.json()["detail"]


def test_expected_return_date_required(client):
    part_id = _stock_part_id(client)
    users = _users(client)
    org = _org(client)
    r = client.post(
        "/api/approvals/loan",
        json={
            "part_id": part_id,
            "dest_org_id": org["id"],
            "approver_ids": [users[1]["id"], users[2]["id"], users[3]["id"]],
        },
        headers=op_headers(users[0]["id"]),
    )
    assert r.status_code == 422


def test_append_only_and_replay(client, db_session):
    assert_no_movement_mutation_api()
    part_id = _stock_part_id(client)
    server_id = _idle_server(client)
    loc_id = _locs(client)[0]["id"]

    client.post(
        f"/api/parts/{part_id}/install",
        json={"server_id": server_id, "slot": "X1"},
        headers=op_headers(1),
    )
    client.post(
        f"/api/parts/{part_id}/uninstall",
        json={"storage_location_id": loc_id},
        headers=op_headers(1),
    )
    part = client.get(f"/api/parts/{part_id}").json()
    replayed = client.get(f"/api/parts/{part_id}/projected-from-log").json()
    assert replayed["matches_cache"] is True
    assert part["current_status"] == replayed["current_status"]
    assert part["current_loc_kind"] == replayed["current_loc_kind"]
    assert part["current_loc_id"] == replayed["current_loc_id"]
    assert "movement_log" in inspect(db_session.bind).get_table_names()


def test_non_designated_approver_rejected(client):
    part_id = _stock_part_id(client)
    users = _users(client)
    applicant, a1, a2, a3, other = (
        users[0],
        users[1],
        users[2],
        users[3],
        users[4],
    )
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

    r = client.post(
        f"/api/approvals/{approval_id}/decide",
        json={"level": 1, "approve": True},
        headers=op_headers(other["id"]),
    )
    assert r.status_code == 400
    assert "指定审批人" in r.json()["detail"]


def test_revalidate_in_stock_before_loan_movement(client):
    part_id = _stock_part_id(client)
    users = _users(client)
    applicant, a1, a2, a3 = users[0], users[1], users[2], users[3]
    org = _org(client)
    server_id = _idle_server(client)

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

    inst = client.post(
        f"/api/parts/{part_id}/install",
        json={"server_id": server_id},
        headers=op_headers(applicant["id"]),
    )
    assert inst.status_code == 200

    client.post(
        f"/api/approvals/{approval_id}/decide",
        json={"level": 1, "approve": True},
        headers=op_headers(a1["id"]),
    )
    client.post(
        f"/api/approvals/{approval_id}/decide",
        json={"level": 2, "approve": True},
        headers=op_headers(a2["id"]),
    )
    final = client.post(
        f"/api/approvals/{approval_id}/decide",
        json={"level": 3, "approve": True},
        headers=op_headers(a3["id"]),
    )
    assert final.status_code == 400
    assert "审批已作废" in final.json()["detail"]

    part = client.get(f"/api/parts/{part_id}").json()
    assert part["current_status"] == enums.STATUS_IN_USE
    moves = client.get(f"/api/parts/{part_id}/movements").json()
    assert all(m["event_type"] != enums.EVENT_LOAN for m in moves)

    approval = client.get(f"/api/approvals/{approval_id}").json()
    assert approval["overall_status"] == enums.APPROVAL_REJECTED


def test_illegal_start_status_install_on_loaned(client):
    part_id = _stock_part_id(client)
    users = _users(client)
    applicant, a1, a2, a3 = users[0], users[1], users[2], users[3]
    org = _org(client)
    server_id = _idle_server(client)

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

    part = client.get(f"/api/parts/{part_id}").json()
    assert part["current_status"] == enums.STATUS_LOANED

    bad = client.post(
        f"/api/parts/{part_id}/install",
        json={"server_id": server_id},
        headers=op_headers(applicant["id"]),
    )
    assert bad.status_code == 400
    assert "非法起始状态" in bad.json()["detail"]


def test_happy_path_full_loan_and_return(client):
    part_id = _stock_part_id(client)
    users = _users(client)
    applicant, a1, a2, a3 = users[0], users[1], users[2], users[3]
    org = _org(client)
    loc_id = _locs(client)[0]["id"]
    expected = date.today() + timedelta(days=14)

    approval_id = client.post(
        "/api/approvals/loan",
        json={
            "part_id": part_id,
            "dest_org_id": org["id"],
            "expected_return_date": str(expected),
            "approver_ids": [a1["id"], a2["id"], a3["id"]],
        },
        headers=op_headers(applicant["id"]),
    ).json()["id"]
    for level, approver in ((1, a1), (2, a2), (3, a3)):
        assert (
            client.post(
                f"/api/approvals/{approval_id}/decide",
                json={"level": level, "approve": True},
                headers=op_headers(approver["id"]),
            ).status_code
            == 200
        )

    part = client.get(f"/api/parts/{part_id}").json()
    assert part["current_status"] == enums.STATUS_LOANED
    moves = client.get(f"/api/parts/{part_id}/movements").json()
    loan = [m for m in moves if m["event_type"] == enums.EVENT_LOAN][-1]
    assert loan["expected_return_date"] == str(expected)
    assert loan["approval_id"] == approval_id

    ret = client.post(
        f"/api/parts/{part_id}/return",
        json={"storage_location_id": loc_id},
        headers=op_headers(applicant["id"]),
    )
    assert ret.status_code == 200
    assert ret.json()["current_status"] == enums.STATUS_IN_STOCK
