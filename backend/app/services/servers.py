"""服务器信息管理（含合同/采购字段）。"""

import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enums
from ..models import Part, PartServerLink, Server, Supplier
from ..csv_util import csv_text, parse_date
from .movement import BusinessError

_INFO_FIELDS = (
    "model",
    "serial_no",
    "location_id",
    "responsible_group",
    "supplier",
    "contract_no",
    "project",
    "owner_unit",
    "warranty_expiry",
    "arrival_date",
    "purchase_amount",
    "disk_slot_count",
    "disk_interface",
    "mem_slot_count",
    "mem_ddr_gens",
    "pcie_slot_count",
    "nvme_slot_count",
    "nvme_interface",
)

_SLOT_INT_FIELDS = (
    "disk_slot_count",
    "mem_slot_count",
    "pcie_slot_count",
    "nvme_slot_count",
)

_ALLOWED_DISK_IFACES = ("SATA", "SAS", "混插", "其他")
_ALLOWED_NVME_IFACES = ("U.2", "M.2", "AIC", "E1.S", "混插", "其他")
_ALLOWED_DDR = ("DDR4", "DDR5")


def _normalize_slot_fields(info: dict) -> dict:
    """校验并规范化插槽规格字段。"""
    out = dict(info)
    for f in _SLOT_INT_FIELDS:
        if f not in out:
            continue
        val = out[f]
        if val is None or val == "":
            out[f] = None
            continue
        try:
            n = int(val)
        except (TypeError, ValueError) as e:
            raise BusinessError(f"{f} 须为非负整数") from e
        if n < 0:
            raise BusinessError(f"{f} 不能为负")
        out[f] = n

    disk_if = (out.get("disk_interface") or "").strip() or None
    if disk_if and disk_if not in _ALLOWED_DISK_IFACES:
        raise BusinessError(
            f"硬盘接口类型仅允许：{' / '.join(_ALLOWED_DISK_IFACES)}"
        )
    out["disk_interface"] = disk_if

    nvme_if = (out.get("nvme_interface") or "").strip() or None
    if nvme_if and nvme_if not in _ALLOWED_NVME_IFACES:
        raise BusinessError(
            f"NVMe 接口类型仅允许：{' / '.join(_ALLOWED_NVME_IFACES)}"
        )
    out["nvme_interface"] = nvme_if

    gens_raw = out.get("mem_ddr_gens")
    if gens_raw is None or gens_raw == "":
        out["mem_ddr_gens"] = None
    else:
        norm: list[str] = []
        for g in str(gens_raw).replace("，", "/").replace(",", "/").split("/"):
            g2 = g.strip().upper()
            if not g2:
                continue
            if not g2.startswith("DDR"):
                g2 = f"DDR{g2}"
            if g2 not in _ALLOWED_DDR:
                raise BusinessError("内存支持代际仅允许 DDR4 / DDR5")
            if g2 not in norm:
                norm.append(g2)
        out["mem_ddr_gens"] = "/".join(norm) if norm else None
    return out


def _validate_common(
    db: Session,
    *,
    asset_no: str,
    responsible_group: Optional[str],
    exclude_id: Optional[int] = None,
) -> str:
    no = (asset_no or "").strip()
    if not no:
        raise BusinessError("服务器资产编号必填")
    stmt = select(Server).where(Server.asset_no == no)
    if exclude_id is not None:
        stmt = stmt.where(Server.id != exclude_id)
    if db.scalars(stmt).first() is not None:
        raise BusinessError(f"服务器资产编号已存在: {no}")
    if responsible_group and responsible_group not in enums.RESPONSIBLE_GROUPS:
        raise BusinessError(f"非法运维部门: {responsible_group}")
    return no


def create_server(
    db: Session,
    *,
    asset_no: str,
    run_status: str = enums.RUN_NOT_LIVE,
    **info,
) -> Server:
    info = _normalize_slot_fields(info)
    no = _validate_common(
        db, asset_no=asset_no, responsible_group=info.get("responsible_group")
    )
    if run_status not in (enums.RUN_NOT_LIVE, enums.RUN_LIVE):
        raise BusinessError("新建服务器运行状态仅允许「未投运」或「投运」")
    row = Server(asset_no=no, run_status=run_status)
    for f in _INFO_FIELDS:
        if f in info:
            row.__setattr__(f, info[f])
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_server(
    db: Session,
    server_id: int,
    *,
    asset_no: Optional[str] = None,
    run_status: Optional[str] = None,
    **info,
) -> Server:
    """档案字段更新。run_status 不可经此接口修改，请用 PATCH /servers/{id}/run-status。"""
    if run_status is not None:
        raise BusinessError("运行状态请通过 PATCH /servers/{id}/run-status 修改")
    # 防御：忽略误传入的 run_status（Schema 已排除；kwargs 兜底）
    info.pop("run_status", None)
    info = _normalize_slot_fields(info)
    row = db.get(Server, server_id)
    if row is None:
        raise BusinessError("服务器不存在")
    if asset_no is not None:
        row.asset_no = _validate_common(
            db,
            asset_no=asset_no,
            responsible_group=None,
            exclude_id=server_id,
        )
    for f in _INFO_FIELDS:
        if f in info:
            val = info[f]
            if f == "responsible_group" and val and val not in enums.RESPONSIBLE_GROUPS:
                raise BusinessError(f"非法运维部门: {val}")
            row.__setattr__(f, val)
    db.commit()
    db.refresh(row)
    return row


def get_server_detail(db: Session, server_id: int) -> dict:
    """服务器档案 + 当前安装在该机上的配件清单。"""
    from sqlalchemy.orm import joinedload

    server = db.get(Server, server_id)
    if server is None:
        raise BusinessError("服务器不存在")

    links = {
        ln.part_id: ln.slot
        for ln in db.scalars(
            select(PartServerLink).where(PartServerLink.server_id == server_id)
        ).all()
    }
    parts = list(
        db.scalars(
            select(Part)
            .options(joinedload(Part.model))
            .where(
                Part.current_loc_kind == enums.LOC_SERVER,
                Part.current_loc_id == server_id,
            )
            .order_by(Part.id)
        )
        .unique()
        .all()
    )
    installed = []
    by_cat: dict[str, int] = {}
    for p in parts:
        cat = (p.model.category if p.model else None) or "未分类"
        by_cat[cat] = by_cat.get(cat, 0) + 1
        installed.append(
            {
                "id": p.id,
                "fixed_asset_no": p.fixed_asset_no,
                "serial_no": p.serial_no,
                "category": cat,
                "model_name": p.model.model_name if p.model else None,
                "brand": p.model.brand if p.model else None,
                "current_status": p.current_status,
                "slot": links.get(p.id),
                "allocatable_flag": p.allocatable_flag,
                "source_type": p.source_type,
            }
        )
    return {
        "server": server,
        "installed_parts": installed,
        "installed_count": len(installed),
        "installed_by_category": by_cat,
    }


def delete_server(db: Session, server_id: int) -> None:
    row = db.get(Server, server_id)
    if row is None:
        raise BusinessError("服务器不存在")
    linked = db.scalars(
        select(PartServerLink.id).where(PartServerLink.server_id == server_id).limit(1)
    ).first()
    if linked is not None:
        raise BusinessError("该服务器上仍有配件安装关系，请先拆下后再删除")
    referenced = db.scalars(
        select(Part.id)
        .where(Part.current_loc_kind == enums.LOC_SERVER, Part.current_loc_id == server_id)
        .limit(1)
    ).first()
    if referenced is not None:
        raise BusinessError("仍有配件定位在该服务器，请先转移后再删除")
    db.delete(row)
    db.commit()


# ================= 批量导入导出（CSV） =================

# 中文表头 ↔ 字段映射（导入模板与导出共用同一列序，单一真相源）
CSV_COLUMNS = [
    ("资产编号", "asset_no"),
    ("型号", "model"),
    ("SN", "serial_no"),
    ("部署位置ID", "location_id"),
    ("运维部门", "responsible_group"),
    ("供应商", "supplier"),
    ("合同号", "contract_no"),
    ("所属项目", "project"),
    ("产权单位", "owner_unit"),
    ("维保到位时间", "warranty_expiry"),
    ("设备到货日期", "arrival_date"),
    ("采购金额", "purchase_amount"),
    ("运行状态", "run_status"),
    ("硬盘插槽数", "disk_slot_count"),
    ("硬盘接口", "disk_interface"),
    ("内存插槽数", "mem_slot_count"),
    ("内存代际", "mem_ddr_gens"),
    ("PCIe插槽数", "pcie_slot_count"),
    ("NVMe插槽数", "nvme_slot_count"),
    ("NVMe接口", "nvme_interface"),
]

_HEADER_TO_FIELD = {h: f for h, f in CSV_COLUMNS}



def export_servers_csv(db: Session) -> str:
    rows = [[h for h, _ in CSV_COLUMNS]]
    for s in db.scalars(select(Server).order_by(Server.id)).all():
        rows.append([str(getattr(s, f) or "") for _, f in CSV_COLUMNS])
    return csv_text(rows)


def import_template_csv() -> str:
    example = [
        "SRV-EXAMPLE-001", "浪潮 NF5280M6", "SN123456", "1",
        "基础组", "浪潮信息", "HT-2026-100", "2026年资源扩容", "本单位信息中心",
        "2029-06-30", "2026-07-01", "185000.00", "未投运",
        "12", "SAS", "32", "DDR5", "8", "4", "U.2",
    ]
    return csv_text([[h for h, _ in CSV_COLUMNS], example])



def parse_servers_csv(db: Session, content: str) -> dict:
    """解析并逐行校验（不写库）。返回 rows 明细供预览/提交复用。"""
    # 去 BOM；统一按 utf-8 解码
    text = content.lstrip("﻿")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise BusinessError("CSV 内容为空")

    header = [h.strip() for h in header]
    unknown = [h for h in header if h not in _HEADER_TO_FIELD]
    if unknown:
        raise BusinessError(f"表头含未知列：{'、'.join(unknown)}（请使用下载的模板）")
    if "资产编号" not in header:
        raise BusinessError("表头缺少必需列：资产编号")

    idx = {h: header.index(h) for h in header}

    def cell(row: list[str], h: str) -> str:
        i = idx.get(h)
        return row[i].strip() if i is not None and i < len(row) else ""

    existing_nos = set(db.scalars(select(Server.asset_no)).all())
    supplier_names = set(db.scalars(select(Supplier.name)).all())

    rows: list[dict] = []
    seen_in_file: set[str] = set()
    for line_no, raw in enumerate(reader, start=2):
        if not any(c.strip() for c in raw):
            continue  # 跳过空行
        errors: list[str] = []
        asset_no = cell(raw, "资产编号")
        if not asset_no:
            errors.append("【资产编号】必填")
        else:
            if asset_no in existing_nos:
                errors.append(f"【资产编号】已存在：{asset_no}")
            if asset_no in seen_in_file:
                errors.append(f"【资产编号】文件内重复：{asset_no}")
            seen_in_file.add(asset_no)

        group = cell(raw, "运维部门")
        if group and group not in enums.RESPONSIBLE_GROUPS:
            errors.append(
                f"【运维部门】「{group}」非法，允许：{'/'.join(enums.RESPONSIBLE_GROUPS)}"
            )

        supplier = cell(raw, "供应商")
        if supplier and supplier not in supplier_names:
            errors.append(f"【供应商】「{supplier}」不在名录中，请先维护")

        run_status = cell(raw, "运行状态") or enums.RUN_NOT_LIVE
        if run_status not in (enums.RUN_NOT_LIVE, enums.RUN_LIVE):
            errors.append(f"【运行状态】仅允许「未投运/投运」，当前「{run_status}」")

        warranty = parse_date(cell(raw, "维保到位时间"), errors, "维保到位时间")
        arrival = parse_date(cell(raw, "设备到货日期"), errors, "设备到货日期")

        amount: Optional[Decimal] = None
        amount_s = cell(raw, "采购金额")
        if amount_s:
            try:
                amount = Decimal(amount_s)
                if amount < 0:
                    errors.append("【采购金额】不能为负")
            except InvalidOperation:
                errors.append(f"【采购金额】「{amount_s}」须为数字")

        loc_id_s = cell(raw, "部署位置ID") or ""
        loc_id = int(loc_id_s) if loc_id_s.isdigit() else None
        disk_count_s = cell(raw, "硬盘插槽数") or "0"
        disk_count = int(disk_count_s) if disk_count_s.isdigit() else 0
        mem_count_s = cell(raw, "内存插槽数") or "0"
        mem_count = int(mem_count_s) if mem_count_s.isdigit() else 0
        pcie_s = cell(raw, "PCIe插槽数") or "0"
        pcie = int(pcie_s) if pcie_s.isdigit() else 0
        nvme_count_s = cell(raw, "NVMe插槽数") or "0"
        nvme_count = int(nvme_count_s) if nvme_count_s.isdigit() else 0

        data = {
            "asset_no": asset_no,
            "model": cell(raw, "型号") or "",
            "serial_no": cell(raw, "SN") or "",
            "location_id": loc_id,
            "responsible_group": group or "",
            "supplier": supplier or "",
            "contract_no": cell(raw, "合同号") or "",
            "project": cell(raw, "所属项目") or "",
            "owner_unit": cell(raw, "产权单位") or "",
            "warranty_expiry": warranty,
            "arrival_date": arrival,
            "purchase_amount": amount,
            "run_status": run_status,
            "disk_slot_count": disk_count,
            "disk_interface": cell(raw, "硬盘接口") or "",
            "mem_slot_count": mem_count,
            "mem_ddr_gens": cell(raw, "内存代际") or "",
            "pcie_slot_count": pcie,
            "nvme_slot_count": nvme_count,
            "nvme_interface": cell(raw, "NVMe接口") or "",
        }
        rows.append({"line": line_no, "ok": not errors, "errors": errors, "data": data})

    if not rows:
        raise BusinessError("CSV 中没有数据行")
    valid = sum(1 for r in rows if r["ok"])
    return {"rows": rows, "total": len(rows), "valid": valid}


def batch_import_servers(db: Session, content: str, *, dry_run: bool) -> dict:
    """两段式导入：dry_run=True 仅校验预览；False 时整批通过才写入。"""
    report = parse_servers_csv(db, content)
    if dry_run:
        return {**report, "created": 0, "committed": False}
    if report["valid"] != report["total"]:
        bad = report["total"] - report["valid"]
        raise BusinessError(f"存在 {bad} 行校验未通过，整批未导入（请修正后重新上传）")
    try:
        for r in report["rows"]:
            db.add(Server(**r["data"]))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {**report, "created": report["total"], "committed": True}
