"""服务器信息管理（含合同字段）测试。"""

from tests.conftest import demo_cast, op_headers


def _new_server_payload(**over):
    base = {
        "asset_no": "SRV-NEW-100",
        "model": "华为 2288H V6",
        "room": "C机房",
        "rack": "C01",
        "u_position": "5U",
        "responsible_group": "网络组",
        "supplier": "华为",
        "contract_no": "HT-2026-200",
        "project": "2026年网络资源池",
        "owner_unit": "本单位信息中心",
        "warranty_expiry": "2029-05-31",
        "arrival_date": "2026-06-01",
        "purchase_amount": "150000.00",
    }
    base.update(over)
    return base


def test_create_server_admin_only(client):
    cast = demo_cast(client)
    r = client.post(
        "/api/servers",
        json=_new_server_payload(),
        headers=op_headers(cast["applicant"]["id"]),  # 操作员
    )
    assert r.status_code == 403

    r2 = client.post(
        "/api/servers",
        json=_new_server_payload(),
        headers=op_headers(cast["admin"]["id"]),
    )
    assert r2.status_code == 200, r2.json()
    data = r2.json()
    assert data["contract_no"] == "HT-2026-200"
    assert data["warranty_expiry"] == "2029-05-31"
    assert data["run_status"] == "未投运"


def test_create_server_duplicate_asset_no(client):
    cast = demo_cast(client)
    r = client.post(
        "/api/servers",
        json=_new_server_payload(asset_no="SRV-LIVE-001"),
        headers=op_headers(cast["admin"]["id"]),
    )
    assert r.status_code == 400
    assert "已存在" in r.json()["detail"]


def test_update_server_info(client):
    cast = demo_cast(client)
    sid = client.post(
        "/api/servers",
        json=_new_server_payload(),
        headers=op_headers(cast["admin"]["id"]),
    ).json()["id"]
    r = client.put(
        f"/api/servers/{sid}",
        json={"room": "D机房", "contract_no": "HT-2026-999", "responsible_group": "平台组"},
        headers=op_headers(cast["admin"]["id"]),
    )
    assert r.status_code == 200
    assert r.json()["room"] == "D机房"
    assert r.json()["contract_no"] == "HT-2026-999"
    assert r.json()["responsible_group"] == "平台组"

    r2 = client.put(
        f"/api/servers/{sid}",
        json={"responsible_group": "不存在的组"},
        headers=op_headers(cast["admin"]["id"]),
    )
    assert r2.status_code == 400


def test_delete_server_guard(client):
    cast = demo_cast(client)
    servers = client.get("/api/servers").json()
    live = next(s for s in servers if s["asset_no"] == "SRV-LIVE-001")
    # 有配件安装关系 → 禁止删除
    r = client.delete(f"/api/servers/{live['id']}", headers=op_headers(cast["admin"]["id"]))
    assert r.status_code == 400
    assert "配件" in r.json()["detail"]

    # 新建空服务器 → 可删
    sid = client.post(
        "/api/servers",
        json=_new_server_payload(),
        headers=op_headers(cast["admin"]["id"]),
    ).json()["id"]
    r2 = client.delete(f"/api/servers/{sid}", headers=op_headers(cast["admin"]["id"]))
    assert r2.status_code == 200


def test_run_status_requires_auth(client):
    servers = client.get("/api/servers").json()
    r = client.patch(
        f"/api/servers/{servers[0]['id']}/run-status",
        json={"run_status": "未投运"},
    )
    assert r.status_code == 401


def test_get_single_server(client):
    servers = client.get("/api/servers").json()
    sid = servers[0]["id"]
    r = client.get(f"/api/servers/{sid}")
    assert r.status_code == 200
    assert r.json()["asset_no"] == servers[0]["asset_no"]
    r2 = client.get("/api/servers/99999")
    assert r2.status_code == 404


# ---------- 批量导入导出 ----------

def _csv_rows(*rows):
    header = "资产编号,型号,SN,机房,机柜,U位,运维部门,供应商,合同号,所属项目,产权单位,维保到位时间,设备到货日期,采购金额,运行状态"
    return "\n".join([header, *rows])


def test_export_and_template(client):
    cast = demo_cast(client)
    h = op_headers(cast["admin"]["id"])
    r = client.get("/api/servers/export.csv", headers=h)
    assert r.status_code == 200
    assert "资产编号" in r.text
    assert "SRV-LIVE-001" in r.text
    r2 = client.get("/api/servers/import-template.csv", headers=h)
    assert "SRV-EXAMPLE-001" in r2.text


def test_batch_import_preview_then_commit(client):
    cast = demo_cast(client)
    h = op_headers(cast["admin"]["id"])
    csv_text = _csv_rows(
        "SRV-BATCH-001,机型A,SN01,A机房,A01,1U,基础组,,HT-1,项目甲,本单位信息中心,2029-01-01,2026-08-01,1000.00,未投运",
        "SRV-BATCH-002,机型B,SN02,B机房,B02,2U,网络组,,HT-2,项目乙,本单位信息中心,,,2000.50,投运",
    )
    # 预览：不写库
    prev = client.post(
        "/api/servers/batch-import?dry_run=true",
        json={"content": csv_text},
        headers=h,
    )
    assert prev.status_code == 200, prev.json()
    body = prev.json()
    assert body["total"] == 2 and body["valid"] == 2 and not body["committed"]
    nos_before = {s["asset_no"] for s in client.get("/api/servers").json()}
    assert "SRV-BATCH-001" not in nos_before

    # 提交：整批写入
    done = client.post(
        "/api/servers/batch-import?dry_run=false",
        json={"content": csv_text},
        headers=h,
    )
    assert done.status_code == 200
    assert done.json()["created"] == 2
    nos_after = {s["asset_no"] for s in client.get("/api/servers").json()}
    assert {"SRV-BATCH-001", "SRV-BATCH-002"} <= nos_after


def test_batch_import_validation_errors(client):
    cast = demo_cast(client)
    h = op_headers(cast["admin"]["id"])
    csv_text = _csv_rows(
        "SRV-LIVE-001,机型A,SN01,A机房,A01,1U,基础组,,,,,,,,未投运",  # 与种子重复
        "SRV-BATCH-003,机型B,SN02,B机房,B02,2U,不存在的组,,,,,not-a-date,,abc,投运",  # 多错
        "SRV-BATCH-003,机型C,SN03,B机房,B02,2U,基础组,,,,,,,,未投运",  # 文件内重复
    )
    r = client.post(
        "/api/servers/batch-import?dry_run=true",
        json={"content": csv_text},
        headers=h,
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert not rows[0]["ok"] and "已存在" in rows[0]["errors"][0]
    assert not rows[1]["ok"]
    joined = "；".join(rows[1]["errors"])
    assert "运维部门" in joined and "日期" in joined and "数字" in joined
    assert not rows[2]["ok"] and "重复" in rows[2]["errors"][0]

    # 有错误行时提交 → 400 整批不入
    r2 = client.post(
        "/api/servers/batch-import?dry_run=false",
        json={"content": csv_text},
        headers=h,
    )
    assert r2.status_code == 400
    nos = {s["asset_no"] for s in client.get("/api/servers").json()}
    assert "SRV-BATCH-003" not in nos


def test_batch_import_role_gate(client):
    cast = demo_cast(client)
    r = client.post(
        "/api/servers/batch-import?dry_run=true",
        json={"content": _csv_rows("SRV-X-1,机型,SN,A机房,A1,1U,基础组,,,,,,,,未投运")},
        headers=op_headers(cast["applicant"]["id"]),  # 操作员
    )
    assert r.status_code == 403
