"""型号管理 / 规格校验 / 遗留迁移。"""

from sqlalchemy import select

from app.models import PartModel
from app.migrate_part_models import migrate_legacy_part_models
from app.services import part_models as part_models_service
from tests.conftest import op_headers


def test_create_model_requires_spec_fields(client):
    bad = client.post(
        "/api/part-models",
        json={"category": "内存", "model_name": "缺字段内存", "spec": {}},
        headers=op_headers(1),
    )
    assert bad.status_code == 400
    assert "必填" in bad.json()["detail"]

    ok = client.post(
        "/api/part-models",
        json={
            "category": "内存",
            "model_name": "完整内存-测试",
            "spec": {"容量GB": 32, "内存类型": "DDR5"},
        },
        headers=op_headers(1),
    )
    assert ok.status_code == 200
    assert ok.json()["spec"]["容量GB"] == 32


def test_forbid_category_change_when_model_in_use(client, db_session):
    # 种子内存型号已被实物引用
    mem = next(m for m in client.get("/api/part-models", headers=op_headers(1)).json() if m["category"] == "内存")
    r = client.put(
        f"/api/part-models/{mem['id']}",
        json={
            "category": "固态硬盘",
            "model_name": mem["model_name"],
            "spec": {"容量GB": 512, "接口协议": "NVMe"},
        },
        headers=op_headers(1),
    )
    assert r.status_code == 400
    assert "禁止变更配件类型" in r.json()["detail"]


def test_allow_category_change_when_unused(client):
    created = client.post(
        "/api/part-models",
        json={
            "category": "网卡",
            "model_name": "临时网卡-可改类型",
            "spec": {"速率": "10G", "口型": "电口", "端口数": 2},
        },
        headers=op_headers(1),
    ).json()
    r = client.put(
        f"/api/part-models/{created['id']}",
        json={
            "category": "光模块",
            "model_name": "临时网卡-可改类型",
            "spec": {"速率": "10G", "类型": "多模SR", "厂商兼容": "通用"},
        },
        headers=op_headers(1),
    )
    assert r.status_code == 200, r.text
    assert r.json()["category"] == "光模块"


def test_update_name_does_not_require_respec(client, db_session):
    mem = next(m for m in client.get("/api/part-models", headers=op_headers(1)).json() if m["category"] == "内存")
    before_spec = dict(mem["spec"])
    # 直接服务层：只改品牌，不传 spec
    updated = part_models_service.update_model(
        db_session, mem["id"], brand="品牌改名测试"
    )
    assert updated.brand == "品牌改名测试"
    assert dict(updated.spec) == before_spec


def test_migrate_gpu_alias_and_incomplete_optic_spec(db_session):
    db_session.add(
        PartModel(
            category="GPU卡",
            model_name="遗留 GPU 40GB",
            brand="NVIDIA",
            pn="LEGACY-GPU",
            spec={"显存GB": 40, "封装": "PCIe"},
        )
    )
    db_session.add(
        PartModel(
            category="光模块",
            model_name="遗留 25G SR",
            brand="通用",
            pn="LEGACY-OPT",
            spec={"类型": "多模SR"},  # 缺速率/兼容
        )
    )
    db_session.commit()

    stats = migrate_legacy_part_models(db_session)
    assert stats["renamed"] >= 1
    assert stats["repaired"] >= 1
    assert stats["failed"] == []

    gpu = db_session.scalars(select(PartModel).where(PartModel.pn == "LEGACY-GPU")).one()
    assert gpu.category == "算力卡"
    assert gpu.spec["显存GB"] == 40

    opt = db_session.scalars(select(PartModel).where(PartModel.pn == "LEGACY-OPT")).one()
    assert opt.spec.get("速率")
    assert opt.spec.get("厂商兼容")

    # 迁移后应能通过入库规格校验
    from app.category_specs import validate_and_normalize_spec

    validate_and_normalize_spec(gpu.category, gpu.spec)
    validate_and_normalize_spec(opt.category, opt.spec)


def test_duplicate_model_name_rejected(client):
    body = {
        "category": "RAID卡",
        "model_name": "重复型号名",
        "spec": {"通道数": 8},
    }
    assert client.post("/api/part-models", json=body, headers=op_headers(1)).status_code == 200
    dup = client.post("/api/part-models", json=body, headers=op_headers(1))
    assert dup.status_code == 400
    assert "已存在" in dup.json()["detail"]
