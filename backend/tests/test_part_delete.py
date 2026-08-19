"""配件误录删除的权限与审计护栏。"""

from app import enums
from tests.conftest import op_headers


def _find_deletable_part(client, headers):
    for part in client.get("/api/parts", headers=headers).json():
        if part["current_status"] != enums.STATUS_IN_STOCK:
            continue
        movements = client.get(
            f"/api/parts/{part['id']}/movements", headers=headers
        ).json()
        if len(movements) == 1 and movements[0]["event_type"] == enums.EVENT_INBOUND:
            return part
    raise AssertionError("种子数据中缺少可用于误录删除测试的未流转配件")


def test_leader_can_delete_unmoved_in_stock_part(client):
    headers = op_headers(1)
    part = _find_deletable_part(client, headers)
    response = client.delete(f"/api/parts/{part['id']}", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True}
    assert client.get(f"/api/parts/{part['id']}", headers=headers).status_code == 404


def test_non_leader_cannot_delete_part(client):
    leader_headers = op_headers(1)
    part = _find_deletable_part(client, leader_headers)
    response = client.delete(
        f"/api/parts/{part['id']}", headers=op_headers(2)
    )
    assert response.status_code == 403


def test_delete_rejects_active_or_historic_asset(client):
    headers = op_headers(1)
    in_use = next(
        part
        for part in client.get("/api/parts", headers=headers).json()
        if part["current_status"] == enums.STATUS_IN_USE
    )
    response = client.delete(f"/api/parts/{in_use['id']}", headers=headers)
    assert response.status_code == 400
    assert "当前为「在用」" in response.json()["detail"]
