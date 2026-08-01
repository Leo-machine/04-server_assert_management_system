"""内存聚合列与 spec 双写辅助。"""

from typing import Optional

from .. import enums
from ..models import PartModel


def sync_memory_aggregate_columns(model: PartModel, spec: Optional[dict] = None) -> None:
    """
    内存型号：从规范化后的 spec 同步 capacity_gb / ddr_gen。
    其它类型：清空聚合列，避免脏数据参与 group by。
    """
    data = spec if spec is not None else (model.spec or {})
    if model.category != "内存":
        model.capacity_gb = None
        model.ddr_gen = None
        return

    cap = data.get("容量GB")
    gen = data.get("内存类型")
    if cap is None:
        model.capacity_gb = None
    else:
        model.capacity_gb = int(cap)
    if gen in enums.DDR_GENS:
        model.ddr_gen = gen
    else:
        model.ddr_gen = None
