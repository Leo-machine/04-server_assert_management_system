"""自助注册 + 领导审批流测试。"""

from tests.conftest import demo_cast, op_headers


def _register(client, **over):
    payload = {
        "username": "newbie01",
        "password": "abc12345",
        "name": "测试新人",
        "applied_role": "主业运维",
        "apply_reason": "新入职，负责备件调配",
    }
    payload.update(over)
    return client.post("/api/auth/register", json=payload)


def _login(client, username, password="abc12345"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_register_pending_then_approve_then_login(client):
    r = _register(client)
    assert r.status_code == 200, r.json()
    assert r.json()["status"] == "待审核"

    # 待审核不能登录
    r1 = _login(client, "newbie01")
    assert r1.status_code == 403
    assert "审批" in r1.json()["detail"]

    # 领导在审批列表看到并通过
    cast = demo_cast(client)
    leader_h = op_headers(cast["admin"]["id"])
    regs = client.get("/api/auth/registrations", headers=leader_h).json()
    target = next(x for x in regs if x["username"] == "newbie01")
    assert target["applied_role"] == "主业运维"
    assert target["apply_reason"] == "新入职，负责备件调配"

    r2 = client.post(f"/api/auth/registrations/{target['id']}/approve", headers=leader_h)
    assert r2.status_code == 200
    assert r2.json()["status"] == "正常"

    # 通过后可登录，角色为申请角色
    r3 = _login(client, "newbie01")
    assert r3.status_code == 200
    assert r3.json()["role"] == "主业运维"


def test_register_reject_flow(client):
    _register(client, username="reject01")
    cast = demo_cast(client)
    leader_h = op_headers(cast["admin"]["id"])
    regs = client.get("/api/auth/registrations", headers=leader_h).json()
    target = next(x for x in regs if x["username"] == "reject01")

    # 驳回必须给理由
    r0 = client.post(
        f"/api/auth/registrations/{target['id']}/reject",
        json={"reason": ""},
        headers=leader_h,
    )
    assert r0.status_code == 400

    r1 = client.post(
        f"/api/auth/registrations/{target['id']}/reject",
        json={"reason": "非本单位人员"},
        headers=leader_h,
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "驳回"

    r2 = _login(client, "reject01")
    assert r2.status_code == 403
    assert "非本单位人员" in r2.json()["detail"]


def test_register_validation(client):
    # 重复用户名
    assert _register(client).status_code == 200
    r = _register(client)
    assert r.status_code == 400 and "占用" in r.json()["detail"]
    # 领导不开放自助申请
    r2 = _register(client, username="boss01", applied_role="领导")
    assert r2.status_code == 400 and "领导" in r2.json()["detail"]
    # 密码太短 / 缺理由 / 非法用户名字符
    assert _register(client, username="pw01", password="123").status_code == 400
    assert _register(client, username="reason01", apply_reason=" ").status_code == 400
    assert _register(client, username="坏人!!").status_code == 400


def test_registration_endpoints_role_gate(client):
    _register(client, username="gate01")
    cast = demo_cast(client)
    # 主业运维无权看注册审批
    op_h = op_headers(cast["applicant"]["id"])
    r = client.get("/api/auth/registrations", headers=op_h)
    assert r.status_code == 403
    regs = client.get(
        "/api/auth/registrations", headers=op_headers(cast["admin"]["id"])
    ).json()
    uid = next(x for x in regs if x["username"] == "gate01")["id"]
    r2 = client.post(f"/api/auth/registrations/{uid}/approve", headers=op_h)
    assert r2.status_code == 403
    # 未登录
    assert client.get("/api/auth/registrations").status_code == 401


def test_approved_token_invalid_after_disable(client, db_session):
    """已通过审批的用户若被停用，旧令牌立即失效。"""
    _register(client, username="tok01")
    cast = demo_cast(client)
    leader_h = op_headers(cast["admin"]["id"])
    regs = client.get("/api/auth/registrations", headers=leader_h).json()
    uid = next(x for x in regs if x["username"] == "tok01")["id"]
    client.post(f"/api/auth/registrations/{uid}/approve", headers=leader_h)
    token = _login(client, "tok01").json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=h).status_code == 200
    # 直接改库模拟停用
    from app.models import User

    u = db_session.get(User, uid)
    u.status = "停用"
    db_session.commit()
    assert client.get("/api/auth/me", headers=h).status_code == 401
