"""配件批量导入导出（CSV 两段式）。"""

from app import enums
from tests.conftest import demo_cast, op_headers

HEADER = "配件类型,型号名称,固定资产编号,设备序列（SN）号,来源,关联服务器,存放位置,运维部门,供应商,合同号,所属项目,产权单位,到货验收日期,维保到位时间,采购金额,可调配标记,备注"


def _csv(*rows):
    return "\n".join([HEADER, *rows])


def _mem_model_name(client) -> str:
    models = client.get("/api/part-models", headers=op_headers(1)).json()
    return next(m for m in models if m["category"] == "内存")["model_name"]


def _loc_label(client) -> str:
    locs = client.get("/api/storage-locations", headers=op_headers(1)).json()
    loc = next(l for l in locs if not l.get("allowed_categories") or "内存" in l["allowed_categories"])
    return f"{loc['warehouse']}/{loc['slot']}"


def test_template_and_export(client):
    h = op_headers(1)
    r = client.get("/api/parts/import-template.csv?category=内存", headers=h)
    assert r.status_code == 200
    assert "服务器原装" in r.text and "独立合同采购" in r.text
    r2 = client.get("/api/parts/export.csv", headers=h)
    assert r2.status_code == 200
    assert "FA-MEM-1001" in r2.text and "当前状态" in r2.text


def test_batch_import_original_and_contract(client):
    cast = demo_cast(client)
    h = op_headers(cast["applicant"]["id"])
    model = _mem_model_name(client)
    loc = _loc_label(client)
    csv_text = _csv(
        f"内存,{model},FA-BI-001,SN-BI-001,服务器原装,SRV-IDLE-002,,,,,,,,,800.00,通用可调,随服务器到货",
        f"内存,{model},FA-BI-002,SN-BI-002,独立合同采购,,{loc},基础组,通用配件供应商,HT-1,项目甲,本单位信息中心,2026-08-01,2029-08-01,900.00,保留,合同采购",
    )
    prev = client.post(
        "/api/parts/batch-import?dry_run=true",
        json={"content": csv_text},
        headers=h,
    )
    assert prev.status_code == 200, prev.json()
    body = prev.json()
    assert body["total"] == 2 and body["valid"] == 2 and not body["committed"]
    nos_preview = {p["fixed_asset_no"] for p in client.get("/api/parts", headers=op_headers(1)).json()}
    assert "FA-BI-001" not in nos_preview  # 预览不写库

    done = client.post(
        "/api/parts/batch-import?dry_run=false",
        json={"content": csv_text},
        headers=h,
    )
    assert done.status_code == 200
    assert done.json()["created"] == 2

    parts = {p["fixed_asset_no"]: p for p in client.get("/api/parts", headers=op_headers(1)).json()}
    p1 = parts["FA-BI-001"]
    assert p1["current_status"] == enums.STATUS_IN_USE
    assert p1["current_loc_kind"] == enums.LOC_SERVER
    assert p1["source_type"] == "服务器原装"
    p2 = parts["FA-BI-002"]
    assert p2["current_status"] == enums.STATUS_IN_STOCK
    assert p2["allocatable_flag"] == "保留"

    # 原装件履历：入库直接在装
    moves = client.get(f"/api/parts/{p1['id']}/movements", headers=op_headers(1)).json()
    assert moves[0]["event_type"] == "入库" and moves[0]["loc_to_kind"] == "服务器"


def test_batch_import_validation_errors(client):
    h = op_headers(1)
    model = _mem_model_name(client)
    csv_text = _csv(
        f"内存,{model},FA-MEM-1001,SN-X1,独立合同采购,,{_loc_label(client)},基础组,通用配件供应商,HT-1,项目,本单位,2026-08-01,2029-08-01,100,通用可调,重复编号",
        f"内存,不存在的型号,FA-BI-010,SN-X2,独立合同采购,,{_loc_label(client)},基础组,通用配件供应商,HT-1,项目,本单位,2026-08-01,2029-08-01,100,通用可调,型号不存在",
        f"内存,{model},FA-BI-011,SN-X3,服务器原装,,,,,,,,,,800.00,通用可调,原装缺服务器",
        f"内存,{model},FA-BI-012,SN-X4,独立合同采购,,{_loc_label(client)},基础组,通用配件供应商,HT-1,项目,本单位,bad-date,2029-08-01,abc,通用可调,日期金额双错",
    )
    r = client.post(
        "/api/parts/batch-import?dry_run=true",
        json={"content": csv_text},
        headers=h,
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert "已存在" in rows[0]["errors"][0]
    assert "型号库" in rows[1]["errors"][0]
    assert any("关联服务器" in e for e in rows[2]["errors"])
    joined = "；".join(rows[3]["errors"])
    assert "日期" in joined and "数字" in joined

    # 有错误行提交 → 400 整批不入
    r2 = client.post(
        "/api/parts/batch-import?dry_run=false",
        json={"content": csv_text},
        headers=h,
    )
    assert r2.status_code == 400
    nos = {p["fixed_asset_no"] for p in client.get("/api/parts", headers=op_headers(1)).json()}
    assert "FA-BI-010" not in nos and "FA-BI-012" not in nos


def test_batch_import_rejects_invalid_source(client):
    """来源仅允许三值；如「赠予」应校验失败并指明字段。"""
    h = op_headers(1)
    model = _mem_model_name(client)
    loc = _loc_label(client)
    csv_text = _csv(
        f"内存,{model},FA-BI-GIFT,SN-GIFT,赠予,,{loc},基础组,通用配件供应商,HT-1,项目,本单位信息中心,2026-08-01,2029-08-01,100,通用可调,赠予件",
    )
    r = client.post(
        "/api/parts/batch-import?dry_run=true",
        json={"content": csv_text},
        headers=h,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] == 0
    errs = "；".join(body["rows"][0]["errors"])
    assert "【来源】" in errs and "赠予" in errs
    assert "独立合同采购" in errs or "服务器原装" in errs

    r2 = client.post(
        "/api/parts/batch-import?dry_run=false",
        json={"content": csv_text},
        headers=h,
    )
    assert r2.status_code == 400
    nos = {p["fixed_asset_no"] for p in client.get("/api/parts", headers=op_headers(1)).json()}
    assert "FA-BI-GIFT" not in nos


def test_batch_import_requires_auth(client):
    r = client.post(
        "/api/parts/batch-import?dry_run=true",
        json={"content": _csv()},
    )
    assert r.status_code == 401


def test_batch_import_requires_data_rows(client):
    h = op_headers(1)
    r = client.post(
        "/api/parts/batch-import?dry_run=true",
        json={"content": HEADER},
        headers=h,
    )
    assert r.status_code == 400
    assert "没有数据行" in r.json()["detail"]
