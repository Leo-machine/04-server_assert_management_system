"""数据完整性：外键强制 / 枚举收紧 / 双写对账。"""
import pytest
from sqlalchemy.exc import IntegrityError

from app import enums
from app.models import PartModel
from app.services.memory_spec import sync_memory_aggregate_columns
from app.services.movement import insert_movement
from tests.conftest import op_headers


# ---------------------------------------------------------------------------
# 修复一：外键真生效
# ---------------------------------------------------------------------------
def test_fk_rejects_orphan_operator(db_session):
    """写入指向不存在用户的 movement_log 应被数据库拒绝。"""
    with pytest.raises(IntegrityError):
        insert_movement(
            db_session,
            part_id=1,
            event_type=enums.EVENT_INBOUND,
            status_from=None,
            status_to=enums.STATUS_IN_STOCK,
            operator_id=99999,
            loc_to_kind=enums.LOC_STORAGE,
            loc_to_id=1,
        )


# ---------------------------------------------------------------------------
# 修复二：必填聚合枚举拒绝非法值
# ---------------------------------------------------------------------------
def test_memory_ddr3_rejected(client):
    """内存代际给 DDR3（不在 strict options 内）应被拒绝。"""
    r = client.post(
        "/api/part-models",
        json={
            "category": "内存",
            "model_name": "测试 DDR3 内存",
            "brand": "通用",
            "spec": {"容量GB": 32, "内存类型": "DDR3", "频率MHz": 1600},
        },
        headers=op_headers(1),
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "代际" in detail or "DDR3" in detail


def test_memory_empty_gen_rejected(client):
    """内存代际为空应被拒绝。"""
    r = client.post(
        "/api/part-models",
        json={
            "category": "内存",
            "model_name": "测试空代际",
            "brand": "通用",
            "spec": {"容量GB": 32},
        },
        headers=op_headers(1),
    )
    assert r.status_code == 400


def test_memory_ddr5_passes_and_lands_in_ddr_gen(client):
    """DDR5 正常通过并落聚合列 ddr_gen。"""
    r = client.post(
        "/api/part-models",
        json={
            "category": "内存",
            "model_name": "DDR5 合法型号",
            "brand": "三星",
            "spec": {"容量GB": 64, "内存类型": "DDR5", "频率MHz": 4800},
        },
        headers=op_headers(1),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["capacity_gb"] == 64
    assert body["ddr_gen"] == "DDR5"


# ---------------------------------------------------------------------------
# 修复三：全量双写对账
# ---------------------------------------------------------------------------
def test_all_models_spec_aggregate_consistency(client):
    """全量 part_model：内存的 spec↔聚合列一致；非内存聚合列为 NULL。"""
    models = client.get("/api/part-models").json()
    assert len(models) > 0, "应至少有一条型号数据"

    for m in models:
        cat = m["category"]
        spec = m["spec"] or {}
        cap = m["capacity_gb"]
        gen = m["ddr_gen"]

        if cat == "内存":
            # spec 中的值应与聚合列一致（非 None 时）
            spec_cap = spec.get("容量GB")
            if spec_cap is not None:
                assert cap == int(spec_cap), (
                    f"型号 id={m['id']} spec.容量GB={spec_cap} ≠ capacity_gb={cap}"
                )
            spec_gen = spec.get("内存类型")
            if spec_gen is not None:
                assert gen == spec_gen, (
                    f"型号 id={m['id']} spec.内存类型={spec_gen} ≠ ddr_gen={gen}"
                )
        else:
            assert cap is None, f"非内存型号 id={m['id']} category={cat} capacity_gb 应为 NULL，实际 {cap}"
            assert gen is None, f"非内存型号 id={m['id']} category={cat} ddr_gen 应为 NULL，实际 {gen}"


def test_sync_updates_aggregate_on_spec_change(db_session, client):
    """修改内存型号的 spec 后重新同步，聚合列应随之更新。"""
    # 新建一条内存型号
    r = client.post(
        "/api/part-models",
        json={
            "category": "内存",
            "model_name": "对账测试用",
            "brand": "三星",
            "spec": {"容量GB": 16, "内存类型": "DDR4", "频率MHz": 3200},
        },
        headers=op_headers(1),
    )
    assert r.status_code == 200
    mid = r.json()["id"]

    # 改 spec 后再同步
    client.put(
        f"/api/part-models/{mid}",
        json={"spec": {"容量GB": 32, "内存类型": "DDR5", "频率MHz": 4800}},
        headers=op_headers(1),
    )
    updated = client.get(f"/api/part-models/{mid}").json()
    assert updated["capacity_gb"] == 32
    assert updated["ddr_gen"] == "DDR5"


def test_sync_strict_false_tolerates_dirty_gen(db_session):
    """迁移路径 strict=False：脏代际清空聚合列，不抛错。"""
    row = PartModel(
        category="内存",
        model_name="脏代际容错",
        brand="通用",
        spec={"容量GB": 8, "内存类型": "DDR3"},
    )
    db_session.add(row)
    db_session.flush()
    sync_memory_aggregate_columns(row, strict=False)
    assert row.capacity_gb == 8
    assert row.ddr_gen is None


def test_sync_strict_true_rejects_dirty_gen(db_session):
    """API 路径 strict=True：脏代际必须暴露。"""
    row = PartModel(
        category="内存",
        model_name="脏代际严格",
        brand="通用",
        spec={"容量GB": 8, "内存类型": "DDR3"},
    )
    with pytest.raises(RuntimeError):
        sync_memory_aggregate_columns(row, strict=True)
