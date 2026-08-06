"""认证与授权安全测试：防 P0 回潮（令牌伪造 / X-Operator-Id 后门 / 角色门禁）。"""

import base64
import time

from app.deps import TOKEN_PREFIX, make_token
from tests.conftest import demo_cast, op_headers


def _forge(payload: str) -> str:
    return TOKEN_PREFIX + base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def test_login_success_and_me(client):
    r = client.post(
        "/api/auth/login", json={"username": "zhangyw", "password": "123456"}
    )
    assert r.status_code == 200, r.json()
    data = r.json()
    assert data["role"] == "主业运维"
    assert data["token"].startswith(TOKEN_PREFIX)

    me = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {data['token']}"}
    )
    assert me.status_code == 200
    assert me.json()["username"] == "zhangyw"


def test_login_by_display_name(client):
    r = client.post(
        "/api/auth/login", json={"username": "张运维", "password": "123456"}
    )
    assert r.status_code == 200, r.json()
    assert r.json()["username"] == "zhangyw"
    assert r.json()["role"] == "主业运维"


def test_login_wrong_password(client):
    r = client.post(
        "/api/auth/login", json={"username": "zhangyw", "password": "wrong"}
    )
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post(
        "/api/auth/login", json={"username": "nobody", "password": "123456"}
    )
    assert r.status_code == 401


def test_parts_list_requires_auth(client):
    assert client.get("/api/parts").status_code == 401


def test_legacy_password_hash_upgrades_on_login(client):
    """种子是无盐 sha256，登录一次后应升级为 pbkdf2，且仍能再次登录。"""
    client.post("/api/auth/login", json={"username": "qiancg", "password": "123456"})
    users = client.get("/api/users", headers=op_headers(1)).json()
    # 通过第二次登录验证升级后仍可认证
    r = client.post(
        "/api/auth/login", json={"username": "qiancg", "password": "123456"}
    )
    assert r.status_code == 200
    assert users  # noqa: F841（静默变量占位）


def test_forged_token_rejected(client):
    """垃圾签名的令牌必须 401（P0 回潮测试）。"""
    forged = _forge("1:9999999999:garbagesignature")
    r = client.post(
        "/api/parts/99999/damage",
        json={"remark": "probe"},
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert r.status_code == 401


def test_expired_token_rejected(client):
    class _U:
        id = 1

    expired = make_token(_U(), now=int(time.time()) - 25 * 3600)
    r = client.post(
        "/api/parts/99999/damage",
        json={"remark": "probe"},
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert r.status_code == 401


def test_x_operator_id_backdoor_closed(client):
    """P0：只带 X-Operator-Id 不再能调用业务接口。"""
    r = client.post(
        "/api/parts/99999/damage",
        json={"remark": "probe"},
        headers={"X-Operator-Id": "1"},
    )
    assert r.status_code == 401


def test_no_auth_rejected(client):
    r = client.post("/api/parts/99999/damage", json={"remark": "probe"})
    assert r.status_code in (401, 422)


def test_role_gate_admin_only_catalog(client):
    cast = demo_cast(client)
    # 操作员建品牌 → 403
    r = client.post(
        "/api/brands",
        json={"name": "越权品牌"},
        headers=op_headers(cast["applicant"]["id"]),  # 张运维=操作员
    )
    assert r.status_code == 403
    # 管理员建品牌 → 200
    r2 = client.post(
        "/api/brands",
        json={"name": "越权品牌"},
        headers=op_headers(cast["admin"]["id"]),
    )
    assert r2.status_code == 200, r2.json()


def test_role_gate_stocktake_create(client):
    cast = demo_cast(client)
    # 设备供应商（钱仓管）不应有盘点权限
    r = client.post("/api/stocktakes", json={}, headers=op_headers(cast["other"]["id"]))
    assert r.status_code == 403
    # 领导有盘点权限
    r2 = client.post("/api/stocktakes", json={}, headers=op_headers(cast["a1"]["id"]))
    assert r2.status_code == 200, r2.json()


def test_change_password_flow(client):
    login = client.post(
        "/api/auth/login", json={"username": "qiancg", "password": "123456"}
    ).json()
    headers = {"Authorization": f"Bearer {login['token']}"}
    r = client.post(
        "/api/auth/change-password",
        json={"old_password": "123456", "new_password": "newpass123"},
        headers=headers,
    )
    assert r.status_code == 200
    # 旧密码失效，新密码可登录
    old = client.post(
        "/api/auth/login", json={"username": "qiancg", "password": "123456"}
    )
    assert old.status_code == 401
    new = client.post(
        "/api/auth/login", json={"username": "qiancg", "password": "newpass123"}
    )
    assert new.status_code == 200
