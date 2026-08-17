"""初始化可渐进扩展的三级资产类别目录。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AssetCategory


def migrate_asset_categories(db: Session) -> None:
    if db.scalars(select(AssetCategory.id).limit(1)).first() is not None:
        return

    roots = [
        AssetCategory(name="数字化类", code="DIGITAL", level=1, sort_order=10),
        AssetCategory(name="计量类", code="METERING", level=1, sort_order=20),
        AssetCategory(name="调度类", code="DISPATCH", level=1, sort_order=30),
    ]
    db.add_all(roots)
    db.flush()

    digital = roots[0]
    level2 = [
        AssetCategory(name="服务器类", code="DIGITAL_SERVER", level=2, parent_id=digital.id, sort_order=10),
        AssetCategory(name="交换机类", code="DIGITAL_SWITCH", level=2, parent_id=digital.id, sort_order=20),
        AssetCategory(name="存储设备类", code="DIGITAL_STORAGE", level=2, parent_id=digital.id, sort_order=30),
    ]
    db.add_all(level2)
    db.flush()

    server = level2[0]
    leaves = ["内存", "机械硬盘", "固态硬盘", "RAID卡", "光模块", "网卡", "HBA卡", "算力卡"]
    db.add_all(
        AssetCategory(
            name=name,
            code=f"DIGITAL_SERVER_{index:02d}",
            level=3,
            parent_id=server.id,
            sort_order=index * 10,
            business_category=name,
        )
        for index, name in enumerate(leaves, start=1)
    )
    db.commit()
