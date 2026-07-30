"""种子数据：打开即可点通主线演示。"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import enums
from .models import (
    ExternalOrg,
    MovementLog,
    Part,
    PartModel,
    PartServerLink,
    Server,
    StorageLocation,
    User,
)
from .services.movement import apply_projection_from_movement, insert_movement


def seed_if_empty(db: Session) -> None:
    if db.scalars(select(User).limit(1)).first() is not None:
        return

    users = [
        User(name="张运维", role_label="运维"),
        User(name="李组长", role_label="组长"),
        User(name="王主管", role_label="主管"),
        User(name="赵经理", role_label="经理"),
        User(name="钱仓管", role_label="仓管"),
    ]
    db.add_all(users)
    db.flush()

    models = [
        PartModel(
            category="内存",
            model_name="三星 32GB DDR5-4800 RDIMM",
            brand="三星",
            pn="M321R4GA3BB6-CQK",
            spec={"容量GB": 32},
        ),
        PartModel(
            category="GPU卡",
            model_name="NVIDIA A100 80GB PCIe",
            brand="NVIDIA",
            pn="NVIDIA-A100-80G",
            spec={"显存GB": 80, "封装": "PCIe"},
        ),
        PartModel(
            category="光模块",
            model_name="通用 25G SR SFP28",
            brand="通用",
            pn="SFP28-25G-SR",
            spec={"类型": "多模SR"},
        ),
    ]
    db.add_all(models)
    db.flush()

    locs = [
        StorageLocation(warehouse="一号库", slot="A-01"),
        StorageLocation(warehouse="一号库", slot="B-02"),
    ]
    db.add_all(locs)
    db.flush()

    servers = [
        Server(
            asset_no="SRV-LIVE-001",
            model="浪潮 NF5280M6",
            room="A机房",
            rack="A01",
            u_position="10U",
            responsible_group="基础组",
            run_status=enums.RUN_LIVE,
        ),
        Server(
            asset_no="SRV-IDLE-002",
            model="戴尔 R750",
            room="B机房",
            rack="B03",
            u_position="20U",
            responsible_group="运营组",
            run_status=enums.RUN_NOT_LIVE,
        ),
    ]
    db.add_all(servers)
    db.flush()

    org = ExternalOrg(
        org_name="兄弟单位信息中心",
        contact="周工",
        contact_info="13800000000",
    )
    db.add(org)
    db.flush()

    operator_id = users[0].id
    now = datetime.now(timezone.utc)

    # 在库件（可用于装机 / 借出）
    stock_parts = [
        Part(
            model_id=models[0].id,
            fixed_asset_no="FA-MEM-1001",
            serial_no="SN-MEM-1001",
            source_type="单独合同",
            contract_no="HT-2026-001",
            purchase_amount=Decimal("800.00"),
            purchase_date=date(2026, 1, 10),
            responsible_group="基础组",
            current_status=enums.STATUS_IN_STOCK,
            current_loc_kind=enums.LOC_STORAGE,
            current_loc_id=locs[0].id,
        ),
        Part(
            model_id=models[2].id,
            fixed_asset_no="FA-OPT-3001",
            serial_no="SN-OPT-3001",
            source_type="随器采购",
            responsible_group="网络组",
            current_status=enums.STATUS_IN_STOCK,
            current_loc_kind=enums.LOC_STORAGE,
            current_loc_id=locs[1].id,
        ),
        Part(
            model_id=models[0].id,
            fixed_asset_no="FA-MEM-1002",
            serial_no="SN-MEM-1002",
            source_type="单独合同",
            responsible_group="基础组",
            current_status=enums.STATUS_IN_STOCK,
            current_loc_kind=enums.LOC_STORAGE,
            current_loc_id=locs[0].id,
        ),
    ]
    db.add_all(stock_parts)
    db.flush()
    for p in stock_parts:
        m = insert_movement(
            db,
            part_id=p.id,
            event_type=enums.EVENT_INBOUND,
            status_from=None,
            status_to=enums.STATUS_IN_STOCK,
            operator_id=operator_id,
            loc_from_kind=enums.LOC_NONE,
            loc_to_kind=enums.LOC_STORAGE,
            loc_to_id=p.current_loc_id,
            occurred_at=now - timedelta(days=30),
            remark="种子入库",
        )
        apply_projection_from_movement(p, m)

    # 投运服务器上的在用件（演示投运锁拆）
    live_part = Part(
        model_id=models[1].id,
        fixed_asset_no="FA-GPU-2001",
        serial_no="SN-GPU-2001",
        source_type="单独合同",
        contract_no="HT-2025-088",
        purchase_amount=Decimal("120000.00"),
        purchase_date=date(2025, 6, 1),
        responsible_group="平台组",
        sensitivity="管控",
        current_status=enums.STATUS_IN_USE,
        current_loc_kind=enums.LOC_SERVER,
        current_loc_id=servers[0].id,
    )
    db.add(live_part)
    db.flush()
    m1 = insert_movement(
        db,
        part_id=live_part.id,
        event_type=enums.EVENT_INBOUND,
        status_from=None,
        status_to=enums.STATUS_IN_STOCK,
        operator_id=operator_id,
        loc_from_kind=enums.LOC_NONE,
        loc_to_kind=enums.LOC_STORAGE,
        loc_to_id=locs[0].id,
        occurred_at=now - timedelta(days=60),
        remark="种子入库",
    )
    apply_projection_from_movement(live_part, m1)
    m2 = insert_movement(
        db,
        part_id=live_part.id,
        event_type=enums.EVENT_INSTALL,
        status_from=enums.STATUS_IN_STOCK,
        status_to=enums.STATUS_IN_USE,
        operator_id=operator_id,
        loc_from_kind=enums.LOC_STORAGE,
        loc_from_id=locs[0].id,
        loc_to_kind=enums.LOC_SERVER,
        loc_to_id=servers[0].id,
        occurred_at=now - timedelta(days=50),
        remark="种子装机到投运服务器",
    )
    apply_projection_from_movement(live_part, m2)
    db.add(
        PartServerLink(part_id=live_part.id, server_id=servers[0].id, slot="GPU0")
    )

    # 未投运服务器上的在用件（可直接演示拆下）
    idle_part = Part(
        model_id=models[0].id,
        fixed_asset_no="FA-MEM-1003",
        serial_no="SN-MEM-1003",
        source_type="随器采购",
        responsible_group="运营组",
        current_status=enums.STATUS_IN_USE,
        current_loc_kind=enums.LOC_SERVER,
        current_loc_id=servers[1].id,
    )
    db.add(idle_part)
    db.flush()
    m3 = insert_movement(
        db,
        part_id=idle_part.id,
        event_type=enums.EVENT_INBOUND,
        status_from=None,
        status_to=enums.STATUS_IN_STOCK,
        operator_id=operator_id,
        loc_from_kind=enums.LOC_NONE,
        loc_to_kind=enums.LOC_STORAGE,
        loc_to_id=locs[1].id,
        occurred_at=now - timedelta(days=40),
    )
    apply_projection_from_movement(idle_part, m3)
    m4 = insert_movement(
        db,
        part_id=idle_part.id,
        event_type=enums.EVENT_INSTALL,
        status_from=enums.STATUS_IN_STOCK,
        status_to=enums.STATUS_IN_USE,
        operator_id=operator_id,
        loc_from_kind=enums.LOC_STORAGE,
        loc_from_id=locs[1].id,
        loc_to_kind=enums.LOC_SERVER,
        loc_to_id=servers[1].id,
        occurred_at=now - timedelta(days=35),
    )
    apply_projection_from_movement(idle_part, m4)
    db.add(
        PartServerLink(part_id=idle_part.id, server_id=servers[1].id, slot="DIMM_A1")
    )

    db.commit()


def assert_no_movement_mutation_api() -> None:
    """测试用：确认 movement 服务未暴露 update/delete。"""
    from .services import movement as movement_mod

    forbidden = {"update_movement", "delete_movement", "remove_movement"}
    exposed = {name for name in dir(movement_mod) if not name.startswith("_")}
    overlap = forbidden & exposed
    if overlap:
        raise RuntimeError(f"movement 服务不应暴露: {overlap}")
