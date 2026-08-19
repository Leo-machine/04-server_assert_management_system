"""固定账号 admin 的系统级权限与业务免审批回归。"""

from datetime import date, timedelta

import pytest


def _admin_headers(client) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["is_super_admin"] is True
    return {"Authorization": f"Bearer {data['token']}"}


@pytest.mark.parametrize(
    ("action", "expected_status", "expected_loc_kind"),
    [
        ("loan", "借出", "外单位"),
        ("transfer", "已调拨", "外单位"),
        ("scrap", "报废", "无"),
    ],
)
def test_admin_business_actions_skip_manual_approval(
    client, action, expected_status, expected_loc_kind
):
    headers = _admin_headers(client)
    parts = client.get("/api/parts", headers=headers).json()
    part = next(
        item
        for item in parts
        if item["current_status"] == "在库" and item.get("model", {}).get("category") != "算力卡"
    )
    org_id = client.get("/api/external-orgs", headers=headers).json()[0]["id"]

    if action == "loan":
        payload = {
            "part_id": part["id"],
            "dest_org_id": org_id,
            "expected_return_date": str(date.today() + timedelta(days=14)),
        }
    elif action == "transfer":
        payload = {"part_id": part["id"], "dest_org_id": org_id}
    else:
        payload = {"part_id": part["id"], "reason_code": "本单位销毁"}

    response = client.post(f"/api/approvals/{action}", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    approval = response.json()
    assert approval["overall_status"] == "通过"
    assert approval["current_level"] == 0
    assert approval["auto_approved"] is True
    assert approval["steps"] == []

    current = client.get(f"/api/parts/{part['id']}", headers=headers).json()
    assert current["current_status"] == expected_status
    assert current["current_loc_kind"] == expected_loc_kind

    movements = client.get(
        f"/api/parts/{part['id']}/movements", headers=headers
    ).json()
    assert movements[-1]["approval_id"] == approval["id"]


def test_regular_user_still_requires_three_approvers(client):
    login = client.post(
        "/api/auth/login",
        json={"username": "zhangyw", "password": "123456"},
    ).json()
    headers = {"Authorization": f"Bearer {login['token']}"}
    part = next(
        item
        for item in client.get("/api/parts", headers=headers).json()
        if item["current_status"] == "在库"
    )
    org_id = client.get("/api/external-orgs", headers=headers).json()[0]["id"]
    response = client.post(
        "/api/approvals/loan",
        json={
            "part_id": part["id"],
            "dest_org_id": org_id,
            "expected_return_date": str(date.today() + timedelta(days=14)),
        },
        headers=headers,
    )
    assert response.status_code == 400
    assert "恰好三级审批人" in response.json()["detail"]
