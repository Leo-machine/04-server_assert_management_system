"""用户管理（领导）：新增用户 / 调整角色与状态 / 护栏。"""

from app import enums
from tests.conftest import demo_cast, op_headers


def _create(client, h, **over):
    payload = {
        "username": "umg01",
        "password": "abc12345",
        "name": "管理创建一号",
        "role": "外委运维",
    }
    payload.update(over)
    return client.post("/api/auth/users", json=payload, headers=h)


def test_admin_create_user_and_login(client):
    cast = demo_cast(client)
    leader_h = op_headers(cast["admin"]["id"])
    r = _create(client, leader_h)
    assert r.status_code == 200, r.json()
    assert r.json()["status"] == "正常"

    # 直接生效，无需审批
    r2 = client.post("/api/auth/login", json={"username": "umg01", "password": "abc12345"})
    assert r2.status_code == 200
    assert r2.json()["role"] == "外委运维"


def test_admin_create_leader_role(client):
    """领导可以创建领导（区别于自助注册）。"""
    cast = demo_cast(client)
    leader_h = op_headers(cast["admin"]["id"])
    r = _create(client, leader_h, username="umg02", role="领导")
    assert r.status_code == 200
    assert r.json()["role"] == "领导"


def test_admin_create_validation_and_gate(client):
    cast = demo_cast(client)
    leader_h = op_headers(cast["admin"]["id"])
    op_h = op_headers(cast["applicant"]["id"])
    # 非领导
    assert _create(client, op_h, username="umg03").status_code == 403
    # 重复用户名 / 非法角色 / 短密码
    assert _create(client, leader_h).status_code == 200
    r = _create(client, leader_h)
    assert r.status_code == 400 and "占用" in r.json()["detail"]
    assert _create(client, leader_h, username="umg04", role="超级管理员").status_code == 400
    assert _create(client, leader_h, username="umg05", password="1").status_code == 400


def test_admin_patch_role_and_status(client):
    cast = demo_cast(client)
    leader_h = op_headers(cast["admin"]["id"])
    uid = _create(client, leader_h, username="umg06").json()["id"]

    # 调角色
    r = client.patch(f"/api/auth/users/{uid}", json={"role": "主业运维"}, headers=leader_h)
    assert r.status_code == 200
    assert r.json()["role"] == "主业运维"

    # 停用 → 登录被拒；启用 → 恢复
    r2 = client.patch(f"/api/auth/users/{uid}", json={"status": "停用"}, headers=leader_h)
    assert r2.status_code == 200
    r3 = client.post("/api/auth/login", json={"username": "umg06", "password": "abc12345"})
    assert r3.status_code == 403 and "停用" in r3.json()["detail"]
    client.patch(f"/api/auth/users/{uid}", json={"status": "正常"}, headers=leader_h)
    assert client.post(
        "/api/auth/login", json={"username": "umg06", "password": "abc12345"}
    ).status_code == 200

    # 非法值
    assert client.patch(f"/api/auth/users/{uid}", json={"role": "不存在"}, headers=leader_h).status_code == 400
    assert client.patch(f"/api/auth/users/{uid}", json={"status": "待审核"}, headers=leader_h).status_code == 400


def test_admin_edit_name_and_reset_password(client):
    cast = demo_cast(client)
    leader_h = op_headers(cast["admin"]["id"])
    uid = _create(client, leader_h, username="umg-reset").json()["id"]

    result = client.patch(
        f"/api/auth/users/{uid}",
        json={"name": "更新后姓名", "password": "newpass123"},
        headers=leader_h,
    )
    assert result.status_code == 200, result.json()
    assert result.json()["name"] == "更新后姓名"
    assert client.post(
        "/api/auth/login",
        json={"username": "umg-reset", "password": "newpass123"},
    ).status_code == 200
    assert client.patch(
        f"/api/auth/users/{uid}", json={"password": "123"}, headers=leader_h
    ).status_code == 400


def test_admin_cannot_modify_self(client):
    cast = demo_cast(client)
    leader_h = op_headers(cast["admin"]["id"])
    me = cast["admin"]["id"]
    r = client.patch(f"/api/auth/users/{me}", json={"role": "主业运维"}, headers=leader_h)
    assert r.status_code == 400
    assert "自己" in r.json()["detail"]


def test_super_admin_is_protected_and_role_changes_take_effect(client):
    """admin 不可降权；普通领导的角色调整仍应对旧令牌即时生效。"""
    cast = demo_cast(client)
    leader_h = op_headers(cast["admin"]["id"])
    admin_id = cast["admin"]["id"]

    # 创建第二个领导并登录
    client.post(
        "/api/auth/users",
        json={"username": "boss2", "password": "abc12345", "name": "第二领导", "role": "领导"},
        headers=leader_h,
    )
    boss2_token = client.post(
        "/api/auth/login", json={"username": "boss2", "password": "abc12345"}
    ).json()["token"]
    boss2_h = {"Authorization": f"Bearer {boss2_token}"}

    # 固定超级管理员不能被其他领导降权或停用。
    r = client.patch(f"/api/auth/users/{admin_id}", json={"role": "主业运维"}, headers=boss2_h)
    assert r.status_code == 400
    assert "超级管理员" in r.json()["detail"]
    disabled = client.patch(f"/api/auth/users/{admin_id}", json={"status": "停用"}, headers=boss2_h)
    assert disabled.status_code == 400

    boss2_id = next(
        u["id"] for u in client.get("/api/auth/users", headers=boss2_h).json()
        if u["username"] == "boss2"
    )
    # admin 降权普通领导 → 旧令牌的角色立即以 DB 为准。
    r5 = client.patch(f"/api/auth/users/{boss2_id}", json={"role": "主业运维"}, headers=leader_h)
    assert r5.status_code == 200
    r6 = client.get("/api/auth/me", headers=boss2_h)
    assert r6.status_code == 200
    assert r6.json()["role"] == "主业运维"
