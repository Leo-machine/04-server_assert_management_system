"""服务器信息管理（含合同/采购字段）。"""

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enums
from ..models import Part, PartServerLink, Server, Supplier
from .movement import BusinessError

_INFO_FIELDS = (
    "model",
    "serial_no",
    "room",
    "rack",
    "u_position",
    "responsible_group",
    "supplier",
    "contract_no",
    "project",
    "owner_unit",
    "warranty_expiry",
    "arrival_date",
    "purchase_amount",
)


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
    if run_status is not None:
        if row.run_status == enums.RUN_RETIRED:
            raise BusinessError("退役服务器不可切换运行状态")
        if run_status not in (enums.RUN_NOT_LIVE, enums.RUN_LIVE):
            raise BusinessError("仅允许在「未投运」与「投运」之间切换")
        row.run_status = run_status
    for f in _INFO_FIELDS:
        if f in info:
            val = info[f]
            if f == "responsible_group" and val and val not in enums.RESPONSIBLE_GROUPS:
                raise BusinessError(f"非法运维部门: {val}")
            row.__setattr__(f, val)
    db.commit()
    db.refresh(row)
    return row


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
    ("机房", "room"),
    ("机柜", "rack"),
    ("U位", "u_position"),
    ("运维部门", "responsible_group"),
    ("供应商", "supplier"),
    ("合同号", "contract_no"),
    ("所属项目", "project"),
    ("产权单位", "owner_unit"),
    ("维保到位时间", "warranty_expiry"),
    ("设备到货日期", "arrival_date"),
    ("采购金额", "purchase_amount"),
    ("运行状态", "run_status"),
]

_HEADER_TO_FIELD = {h: f for h, f in CSV_COLUMNS}


def _csv_text(rows: list[list[str]]) -> str:
    """UTF-8 BOM，Excel/WPS 直接打开不乱码。"""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    for r in rows:
        w.writerow(r)
    return "﻿" + buf.getvalue()


def export_servers_csv(db: Session) -> str:
    rows = [[h for h, _ in CSV_COLUMNS]]
    for s in db.scalars(select(Server).order_by(Server.id)).all():
        rows.append([str(getattr(s, f) or "") for _, f in CSV_COLUMNS])
    return _csv_text(rows)


def import_template_csv() -> str:
    example = [
        "SRV-EXAMPLE-001", "浪潮 NF5280M6", "SN123456", "A机房", "A01", "10U",
        "基础组", "浪潮信息", "HT-2026-100", "2026年资源扩容", "本单位信息中心",
        "2029-06-30", "2026-07-01", "185000.00", "未投运",
    ]
    return _csv_text([[h for h, _ in CSV_COLUMNS], example])


def _parse_date(val: str, errors: list[str], header: str) -> Optional[date]:
    """接受 YYYY-MM-DD 与 Excel/WPS 常见的 YYYY/M/D、YYYY.M.D。"""
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    errors.append(f"{header}「{val}」须为日期（如 2026-08-01）")
    return None


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
            errors.append("资产编号必填")
        else:
            if asset_no in existing_nos:
                errors.append(f"资产编号已存在：{asset_no}")
            if asset_no in seen_in_file:
                errors.append(f"文件内资产编号重复：{asset_no}")
            seen_in_file.add(asset_no)

        group = cell(raw, "运维部门")
        if group and group not in enums.RESPONSIBLE_GROUPS:
            errors.append(f"非法运维部门「{group}」，允许：{'/'.join(enums.RESPONSIBLE_GROUPS)}")

        supplier = cell(raw, "供应商")
        if supplier and supplier not in supplier_names:
            errors.append(f"供应商「{supplier}」不在名录中，请先维护")

        run_status = cell(raw, "运行状态") or enums.RUN_NOT_LIVE
        if run_status not in (enums.RUN_NOT_LIVE, enums.RUN_LIVE):
            errors.append(f"运行状态仅允许「未投运/投运」，当前「{run_status}」")

        warranty = _parse_date(cell(raw, "维保到位时间"), errors, "维保到位时间")
        arrival = _parse_date(cell(raw, "设备到货日期"), errors, "设备到货日期")

        amount: Optional[Decimal] = None
        amount_s = cell(raw, "采购金额")
        if amount_s:
            try:
                amount = Decimal(amount_s)
                if amount < 0:
                    errors.append("采购金额不能为负")
            except InvalidOperation:
                errors.append(f"采购金额「{amount_s}」须为数字")

        data = {
            "asset_no": asset_no,
            "model": cell(raw, "型号") or None,
            "serial_no": cell(raw, "SN") or None,
            "room": cell(raw, "机房") or None,
            "rack": cell(raw, "机柜") or None,
            "u_position": cell(raw, "U位") or None,
            "responsible_group": group or None,
            "supplier": supplier or None,
            "contract_no": cell(raw, "合同号") or None,
            "project": cell(raw, "所属项目") or None,
            "owner_unit": cell(raw, "产权单位") or None,
            "warranty_expiry": warranty,
            "arrival_date": arrival,
            "purchase_amount": amount,
            "run_status": run_status,
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
