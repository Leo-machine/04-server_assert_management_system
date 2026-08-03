"""内存聚合列与 spec 双写辅助。"""

from typing import Optional

from .. import enums
from ..models import PartModel


def sync_memory_aggregate_columns(
    model: PartModel,
    spec: Optional[dict] = None,
    *,
    strict: bool = True,
) -> None:
    """
    内存型号：从规范化后的 spec 同步 capacity_gb / ddr_gen。
    其它类型：清空聚合列，避免脏数据参与 group by。

    strict=True（默认，API 写路径）：代际非法则抛错，防止静默脏写。
    strict=False（启动迁移）：非法/缺失代际时清空 ddr_gen 并跳过，不拖垮进程。
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
        return

    model.ddr_gen = None
    if not strict:
        return
    raise RuntimeError(
        f"内存型号 id={model.id} 代际「{gen}」不在 {enums.DDR_GENS} 中，"
        f"聚合列 ddr_gen 无法确定（请先通过规格校验或修复数据）"
    )
