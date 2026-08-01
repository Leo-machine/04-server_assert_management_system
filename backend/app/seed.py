"""种子数据：打开即可点通主线演示。"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import enums
from .migrate_brands import DEFAULT_BRAND_CATEGORIES
from .models import (
    Brand,
    ExternalOrg,
    MovementLog,
    Part,
    PartModel,
    PartServerLink,
    Server,
    StorageLocation,
    Supplier,
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

    brands = [
        Brand(name=name, categories=cats or None)
        for name, cats in DEFAULT_BRAND_CATEGORIES.items()
    ]
    db.add_all(brands)
    db.flush()

    suppliers = [
        Supplier(name="三星代理商", contact="陈经理", contact_info="13800001111"),
        Supplier(name="浪潮渠道", contact="刘工", contact_info="13800002222"),
        Supplier(name="戴尔授权经销商", contact="王经理", contact_info="13800003333"),
        Supplier(name="通用配件供应商", contact="赵仓", contact_info="13800004444"),
    ]
    db.add_all(suppliers)
    db.flush()

    models = [
        PartModel(
            category="内存",
            model_name="三星 32GB DDR4-3200 RDIMM",
            brand="三星",
            pn="M393A4K40EB3-CWE",
            spec={"容量GB": 32, "内存类型": "DDR4", "频率MHz": 3200},
            capacity_gb=32,
            ddr_gen="DDR4",
        ),
        PartModel(
            category="内存",
            model_name="海力士 32GB DDR4-3200 RDIMM",
            brand="海力士",
            pn="HMA84GR7CJR4N-XN",
            spec={"容量GB": 32, "内存类型": "DDR4", "频率MHz": 3200},
            capacity_gb=32,
            ddr_gen="DDR4",
        ),
        PartModel(
            category="机械硬盘",
            model_name="希捷 4TB SAS 7.2K",
            brand="希捷",
            pn="ST4000NM002A",
            spec={"容量TB": 4, "接口": "SAS", "转速": "7200"},
        ),
        PartModel(
            category="固态硬盘",
            model_name="三星 PM9A3 1.92TB NVMe",
            brand="三星",
            pn="MZQL21T9HCJR",
            spec={"容量GB": 1920, "接口协议": "NVMe", "形态": "U.2"},
        ),
        PartModel(
            category="RAID卡",
            model_name="Broadcom MegaRAID 9560-8i",
            brand="Broadcom",
            pn="05-50013-00",
            spec={"通道数": 8, "缓存MB": 4096, "支持RAID级别": "0/1/5/6/10"},
        ),
        PartModel(
            category="光模块",
            model_name="通用 25G SR SFP28",
            brand="通用",
            pn="SFP28-25G-SR",
            spec={"速率": "25G", "类型": "多模SR", "厂商兼容": "通用"},
        ),
        PartModel(
            category="网卡",
            model_name="Mellanox ConnectX-6 Dx 25G",
            brand="Mellanox",
            pn="MCX623106AN-CDAT",
            spec={"速率": "25G", "口型": "光口", "端口数": 2},
        ),
        PartModel(
            category="HBA卡",
            model_name="Broadcom 9500-8e SAS HBA",
            brand="Broadcom",
            pn="05-50011-00",
            spec={"子类型": "SAS-HBA", "速率": "12G-SAS", "端口数": 8},
        ),
        PartModel(
            category="算力卡",
            model_name="NVIDIA A100 80GB PCIe",
            brand="NVIDIA",
            pn="NVIDIA-A100-80G",
            spec={"显存GB": 80, "封装": "PCIe", "架构": "Ampere"},
        ),
    ]
    db.add_all(models)
    db.flush()

    locs = [
        StorageLocation(warehouse="一号库房", slot="A-01", location_type="库房货架", allowed_categories=None),
        StorageLocation(warehouse="A栋数据中心", slot="Rack-B-03", location_type="机房备件柜", allowed_categories=None),
        StorageLocation(warehouse="一号库房", slot="C-03", location_type="库房货架", allowed_categories=["内存", "固态硬盘"]),
        StorageLocation(warehouse="A栋数据中心", slot="Rack-D-12", location_type="数据中心机柜", allowed_categories=["GPU卡", "算力卡"]),
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

    # 在库件（可用于装机 / 借出 / 可调余量演示）
    # 内存可调口径：在库 ∩ 本单位信息中心 ∩ 通用可调 → 1001+2001=2（跨品牌同规格聚合）
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
            supplier="三星代理商",
            project="机房扩容-2026",
            owner_unit=enums.HOME_OWNER_UNIT,
            warranty_expiry=date(2029, 1, 10),
            allocatable_flag=enums.ALLOC_GENERAL,
            current_status=enums.STATUS_IN_STOCK,
            current_loc_kind=enums.LOC_STORAGE,
            current_loc_id=locs[0].id,
        ),
        Part(
            model_id=models[5].id,  # 光模块
            fixed_asset_no="FA-OPT-3001",
            serial_no="SN-OPT-3001",
            source_type="随器采购",
            responsible_group="网络组",
            owner_unit=enums.HOME_OWNER_UNIT,
            allocatable_flag=enums.ALLOC_GENERAL,
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
            owner_unit=enums.HOME_OWNER_UNIT,
            allocatable_flag=enums.ALLOC_RESERVED,  # 保留，不计入可调余量
            current_status=enums.STATUS_IN_STOCK,
            current_loc_kind=enums.LOC_STORAGE,
            current_loc_id=locs[0].id,
        ),
        Part(
            model_id=models[1].id,  # 海力士同规格，跨型号聚合
            fixed_asset_no="FA-MEM-2001",
            serial_no="SN-MEM-2001",
            source_type="单独合同",
            responsible_group="基础组",
            owner_unit=enums.HOME_OWNER_UNIT,
            allocatable_flag=enums.ALLOC_GENERAL,
            current_status=enums.STATUS_IN_STOCK,
            current_loc_kind=enums.LOC_STORAGE,
            current_loc_id=locs[0].id,
        ),
        Part(
            model_id=models[0].id,
            fixed_asset_no="FA-MEM-1004",
            serial_no="SN-MEM-1004",
            source_type="单独合同",
            responsible_group="基础组",
            owner_unit="外单位托管资产",  # 非本单位，不计入
            allocatable_flag=enums.ALLOC_GENERAL,
            current_status=enums.STATUS_IN_STOCK,
            current_loc_kind=enums.LOC_STORAGE,
            current_loc_id=locs[1].id,
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
        model_id=models[8].id,  # 算力卡
        fixed_asset_no="FA-GPU-2001",
        serial_no="SN-GPU-2001",
        source_type="单独合同",
        contract_no="HT-2025-088",
        purchase_amount=Decimal("120000.00"),
        purchase_date=date(2025, 6, 1),
        responsible_group="平台组",
        sensitivity="管控",
        owner_unit=enums.HOME_OWNER_UNIT,
        allocatable_flag=enums.ALLOC_RESERVED,
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

    # 未投运服务器上的在用件（可直接演示拆下；在用不计入可调）
    idle_part = Part(
        model_id=models[0].id,
        fixed_asset_no="FA-MEM-1003",
        serial_no="SN-MEM-1003",
        source_type="随器采购",
        responsible_group="运营组",
        owner_unit=enums.HOME_OWNER_UNIT,
        allocatable_flag=enums.ALLOC_GENERAL,
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
