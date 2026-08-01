"""配件型号遗留数据迁移：类型更名 + 补齐残缺 spec，保证入库校验可通过。"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .category_specs import (
    PART_CATEGORIES,
    SpecValidationError,
    validate_and_normalize_spec,
)
from .models import PartModel
from .services.memory_spec import sync_memory_aggregate_columns

logger = logging.getLogger(__name__)

# 历史类型别名 → 现行类型
CATEGORY_ALIASES = {
    "GPU卡": "算力卡",
    "GPU": "算力卡",
}


def _guess_number_from_text(text: str, patterns: list[str]) -> Optional[float]:
    for pat in patterns:
        m = re.search(pat, text or "", re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except (TypeError, ValueError):
                continue
    return None


def _default_required_spec(category: str, model: PartModel, spec: dict) -> dict:
    """为缺失的必填规格填可推断/保守默认值，尽量保留已有键。"""
    out = dict(spec or {})
    name = model.model_name or ""
    brand = model.brand or ""
    blob = f"{brand} {name} {model.pn or ''}"

    if category == "内存":
        out.setdefault(
            "容量GB",
            _guess_number_from_text(blob, [r"(\d+)\s*GB", r"(\d+)G\b"]) or 16,
        )
        if "DDR5" in blob.upper():
            out.setdefault("内存类型", "DDR5")
        else:
            out.setdefault("内存类型", "DDR4")

    elif category == "机械硬盘":
        out.setdefault(
            "容量TB",
            _guess_number_from_text(blob, [r"(\d+(?:\.\d+)?)\s*TB"]) or 1,
        )
        out.setdefault("接口", "SAS" if "SAS" in blob.upper() else "SATA")

    elif category == "固态硬盘":
        tb = _guess_number_from_text(blob, [r"(\d+(?:\.\d+)?)\s*TB"])
        if tb is not None:
            out.setdefault("容量GB", int(tb * 1000))
        else:
            out.setdefault(
                "容量GB",
                _guess_number_from_text(blob, [r"(\d+)\s*GB"]) or 512,
            )
        if "NVME" in blob.upper():
            out.setdefault("接口协议", "NVMe")
        elif "SAS" in blob.upper():
            out.setdefault("接口协议", "SAS")
        else:
            out.setdefault("接口协议", "SATA")

    elif category == "RAID卡":
        out.setdefault(
            "通道数",
            _guess_number_from_text(blob, [r"(\d+)\s*i\b", r"(\d+)\s*口"]) or 8,
        )

    elif category == "光模块":
        for rate in ("400G", "200G", "100G", "40G", "25G", "10G", "1G"):
            if rate.lower() in blob.lower() or rate in blob:
                out.setdefault("速率", rate)
                break
        out.setdefault("速率", "25G")
        for t in ("DAC", "AOC", "单模LR", "多模SR"):
            if t in name or t in blob:
                out.setdefault("类型", t)
                break
        out.setdefault("类型", "多模SR")
        for vendor in ("华为", "思科", "H3C", "通用"):
            if vendor in blob:
                out.setdefault("厂商兼容", vendor)
                break
        out.setdefault("厂商兼容", "通用")

    elif category == "网卡":
        for rate in ("100G", "40G", "25G", "10G", "1G"):
            if rate.lower() in blob.lower() or rate in blob:
                out.setdefault("速率", rate)
                break
        out.setdefault("速率", "10G")
        out.setdefault(
            "口型", "光口" if ("光" in blob or "SFP" in blob.upper()) else "电口"
        )
        out.setdefault(
            "端口数",
            _guess_number_from_text(blob, [r"(\d+)\s*口", r"x(\d+)\b"]) or 2,
        )

    elif category == "HBA卡":
        out.setdefault(
            "子类型",
            "FC-HBA" if "FC" in blob.upper() else "SAS-HBA",
        )
        for rate in ("24G-SAS", "12G-SAS", "32G", "16G", "8G"):
            if rate.lower() in blob.lower() or rate in blob:
                out.setdefault("速率", rate)
                break
        out.setdefault(
            "速率", "12G-SAS" if out.get("子类型") == "SAS-HBA" else "16G"
        )
        out.setdefault(
            "端口数",
            _guess_number_from_text(blob, [r"(\d+)\s*e\b", r"(\d+)\s*口"]) or 8,
        )

    elif category == "算力卡":
        out.setdefault(
            "显存GB",
            _guess_number_from_text(blob, [r"(\d+)\s*GB"]) or 16,
        )
        out.setdefault("封装", "SXM" if "SXM" in blob.upper() else "PCIe")

    return out


def migrate_legacy_part_models(db: Session) -> dict[str, Any]:
    """
    幂等迁移：
    1) 历史类型别名（如 GPU卡 → 算力卡）
    2) 补齐残缺必填 spec 并规范化
    """
    rows = list(db.scalars(select(PartModel).order_by(PartModel.id)).all())
    renamed = 0
    repaired = 0
    failed: list[dict[str, Any]] = []

    for row in rows:
        new_cat = CATEGORY_ALIASES.get(row.category, row.category)
        if new_cat != row.category:
            row.category = new_cat
            renamed += 1

        if row.category not in PART_CATEGORIES:
            failed.append(
                {
                    "id": row.id,
                    "model_name": row.model_name,
                    "reason": f"未知类型「{row.category}」",
                }
            )
            continue

        before = dict(row.spec or {})
        try:
            normalized = validate_and_normalize_spec(row.category, before)
        except SpecValidationError:
            filled = _default_required_spec(row.category, row, before)
            try:
                normalized = validate_and_normalize_spec(row.category, filled)
            except SpecValidationError as e:
                failed.append(
                    {
                        "id": row.id,
                        "model_name": row.model_name,
                        "reason": e.message,
                    }
                )
                continue

        if normalized != before:
            row.spec = normalized
            repaired += 1
        else:
            row.spec = normalized
        sync_memory_aggregate_columns(row, normalized)

    db.commit()
    if renamed or repaired or failed:
        logger.info(
            "part_model 迁移完成: renamed=%s repaired=%s failed=%s",
            renamed,
            repaired,
            len(failed),
        )
        if failed:
            logger.warning("part_model 迁移失败条目: %s", failed)
    return {"renamed": renamed, "repaired": repaired, "failed": failed}
