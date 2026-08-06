"""配件批量导入导出（CSV）。两段式：预览校验（不写库）→ 整批通过才入库。

导入语义与手工入库完全一致：每行最终都走 services.parts.inbound
（含履历写入、库位类别校验、原装机绑定等全部规则）。
"""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enums
from ..models import (
    ExternalOrg,
    Part,
    PartModel,
    Server,
    StorageLocation,
    Supplier,
)
from ..csv_util import csv_text, parse_date
from .movement import BusinessError
from . import parts as parts_service

# 中文表头 ↔ 字段（模板/导出/导入共用，单一真相源）
CSV_COLUMNS = [
    ("配件类型", "category"),
    ("型号名称", "model_name"),
    ("固定资产编号", "fixed_asset_no"),
    ("设备序列（SN）号", "serial_no"),
    ("来源", "source_type"),
    ("关联服务器", "server_asset_no"),
    ("存放位置", "location"),
    ("运维部门", "responsible_group"),
    ("供应商", "supplier"),
    ("合同号", "contract_no"),
    ("所属项目", "project"),
    ("产权单位", "owner_unit"),
    ("到货验收日期", "purchase_date"),
    ("维保到位时间", "warranty_expiry"),
    ("采购金额", "purchase_amount"),
    ("可调配标记", "allocatable_flag"),
    ("备注", "remark"),
]
_HEADER_TO_FIELD = {h: f for h, f in CSV_COLUMNS}
# 旧表头别名（兼容历史模板）
_HEADER_ALIASES = {"采购日期": "到货验收日期"}

# 非原装来源的必填列
_MANUAL_REQUIRED = (
    "存放位置",
    "运维部门",
    "供应商",
    "合同号",
    "所属项目",
    "产权单位",
    "到货验收日期",
    "维保到位时间",
)



def import_template_csv(db: Session, category: Optional[str] = None) -> str:
    """模板示例行使用库中真实数据（型号/兼容库位/供应商/服务器），
    保证用户照示例填写即可通过校验，而不是占位符。"""
    cat = category or "内存"

    model = db.scalars(
        select(PartModel)
        .where(PartModel.category == cat)
        .order_by(PartModel.id)
    ).first()
    model_name = model.model_name if model else "（先在型号管理中维护本类型号）"

    # 第一个兼容该品类的库位（无限制或显式包含）
    loc_label = ""
    for l in db.scalars(select(StorageLocation).order_by(StorageLocation.id)).all():
        allowed = l.allowed_categories or []
        if not allowed or cat in allowed:
            loc_label = f"{l.warehouse}/{l.slot}"
            break

    supplier = db.scalars(select(Supplier.name).order_by(Supplier.id)).first() or ""
    server = db.scalars(select(Server).order_by(Server.id)).first()
    server_no = server.asset_no if server else ""

    example_original = [
        cat, model_name, "FA-EXAMPLE-001", "SN-EXAMPLE-001",
        "服务器原装", server_no, "", "", "", "", "", "", "", "",
        "800.00", "通用可调", "随服务器到货",
    ]
    example_contract = [
        cat, model_name, "FA-EXAMPLE-002", "SN-EXAMPLE-002",
        "独立合同采购", "", loc_label, "基础组", supplier,
        "HT-2026-001", "2026年资源扩容", "本单位信息中心", "2026-08-01",
        "2029-08-01", "800.00", "通用可调", "合同采购到货",
    ]
    return csv_text([[h for h, _ in CSV_COLUMNS], example_original, example_contract])


def export_parts_csv(
    db: Session, *, category: Optional[str] = None
) -> str:
    stmt = select(Part).join(Part.model).order_by(Part.id)
    if category:
        stmt = stmt.where(PartModel.category == category)
    servers = {s.id: s for s in db.scalars(select(Server)).all()}
    locs = {l.id: l for l in db.scalars(select(StorageLocation)).all()}

    def loc_label(p: Part) -> str:
        if p.current_loc_kind == enums.LOC_STORAGE:
            l = locs.get(p.current_loc_id)
            return f"{l.warehouse}/{l.slot}" if l else ""
        if p.current_loc_kind == enums.LOC_SERVER:
            s = servers.get(p.current_loc_id)
            return s.asset_no if s else ""
        if p.current_loc_kind == enums.LOC_EXTERNAL:
            org = db.get(ExternalOrg, p.current_loc_id)
            return org.org_name if org else ""
        return ""

    header = [h for h, _ in CSV_COLUMNS] + ["当前状态", "当前位置"]
    rows = [header]
    for p in db.scalars(stmt).all():
        rows.append(
            [
                p.model.category if p.model else "",
                p.model.model_name if p.model else "",
                p.fixed_asset_no,
                p.serial_no or "",
                p.source_type or "",
                servers[p.current_loc_id].asset_no
                if p.current_loc_kind == enums.LOC_SERVER and p.current_loc_id in servers
                else "",
                loc_label(p) if p.current_loc_kind == enums.LOC_STORAGE else "",
                p.responsible_group or "",
                p.supplier or "",
                p.contract_no or "",
                p.project or "",
                p.owner_unit or "",
                str(p.purchase_date or ""),
                str(p.warranty_expiry or ""),
                str(p.purchase_amount or ""),
                p.allocatable_flag or "",
                "",
                p.current_status or "",
                loc_label(p),
            ]
        )
    return csv_text(rows)



def parse_parts_csv(db: Session, content: str) -> dict:
    text = content.lstrip("﻿")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise BusinessError("CSV 内容为空")
    header = [_HEADER_ALIASES.get(h.strip(), h.strip()) for h in header]
    unknown = [h for h in header if h not in _HEADER_TO_FIELD]
    if unknown:
        raise BusinessError(f"表头含未知列：{'、'.join(unknown)}（请使用下载的模板）")
    for required in ("配件类型", "型号名称", "固定资产编号", "设备序列（SN）号", "来源", "采购金额", "可调配标记", "备注"):
        if required not in header:
            raise BusinessError(f"表头缺少必需列：{required}")

    idx = {h: header.index(h) for h in header}

    def cell(row: list[str], h: str) -> str:
        i = idx.get(h)
        return row[i].strip() if i is not None and i < len(row) else ""

    models = list(db.scalars(select(PartModel)).all())
    model_by_cn = {(m.category, (m.model_name or "").strip()): m for m in models}
    existing_nos = set(db.scalars(select(Part.fixed_asset_no)).all())
    server_by_no = {s.asset_no: s for s in db.scalars(select(Server)).all()}
    loc_by_label = {f"{l.warehouse}/{l.slot}": l for l in db.scalars(select(StorageLocation)).all()}
    supplier_names = set(db.scalars(select(Supplier.name)).all())

    rows: list[dict] = []
    seen_in_file: set[str] = set()
    for line_no, raw in enumerate(reader, start=2):
        if not any(c.strip() for c in raw):
            continue
        errors: list[str] = []

        cat = cell(raw, "配件类型")
        model_name = cell(raw, "型号名称")
        model = model_by_cn.get((cat, model_name))
        if not cat or not model_name:
            errors.append("【配件类型/型号名称】必填")
        elif model is None:
            errors.append(f"【型号名称】「{cat}/{model_name}」不在型号库，请先维护")
        elif model.category == "服务器":
            errors.append("【配件类型】服务器整机请走「服务器管理」建档，不走配件入库")

        asset_no = cell(raw, "固定资产编号")
        is_auto_asset = not asset_no
        if not is_auto_asset:
            if asset_no in existing_nos:
                errors.append(f"【固定资产编号】已存在：{asset_no}")
            if asset_no in seen_in_file:
                errors.append(f"【固定资产编号】文件内重复：{asset_no}")
            seen_in_file.add(asset_no)

        serial_no = cell(raw, "设备序列（SN）号")
        if not serial_no:
            errors.append("【设备序列（SN）号】必填")

        source = cell(raw, "来源")
        if not source:
            errors.append("【来源】必填")
        elif source not in enums.SOURCE_TYPES:
            errors.append(
                f"【来源】「{source}」不在允许范围内，仅允许："
                f"{' / '.join(enums.SOURCE_TYPES)}"
            )

        flag = cell(raw, "可调配标记")
        if not flag:
            errors.append("【可调配标记】必填")
        elif flag not in enums.ALLOCATABLE_FLAGS:
            errors.append(
                f"【可调配标记】「{flag}」非法，允许：{' / '.join(enums.ALLOCATABLE_FLAGS)}"
            )

        remark = cell(raw, "备注")
        if not remark:
            errors.append("【备注】必填")

        amount: Optional[Decimal] = None
        amount_s = cell(raw, "采购金额")
        if not amount_s:
            errors.append("【采购金额】必填")
        else:
            try:
                amount = Decimal(amount_s)
                if amount < 0:
                    errors.append("【采购金额】不能为负")
            except InvalidOperation:
                errors.append(f"【采购金额】「{amount_s}」须为数字")

        server: Optional[Server] = None
        loc: Optional[StorageLocation] = None
        group = cell(raw, "运维部门")
        supplier = cell(raw, "供应商")
        contract_no = cell(raw, "合同号")
        project = cell(raw, "所属项目")
        owner_unit = cell(raw, "产权单位")
        purchase_date: Optional[date] = None
        warranty: Optional[date] = None

        if source == enums.SOURCE_ORIGINAL:
            sno = cell(raw, "关联服务器")
            if not sno:
                errors.append("【关联服务器】来源为服务器原装时必填（填服务器资产编号）")
            else:
                server = server_by_no.get(sno)
                if server is None:
                    errors.append(f"【关联服务器】「{sno}」不存在")
                else:
                    for label, val in (
                        ("供应商", server.supplier),
                        ("合同号", server.contract_no),
                        ("运维部门", server.responsible_group),
                    ):
                        if not (val or "").strip():
                            errors.append(
                                f"【关联服务器】「{sno}」档案缺少{label}，请先在服务器管理补全"
                            )
        elif source in enums.SOURCE_TYPES:
            for h in _MANUAL_REQUIRED:
                if not cell(raw, h):
                    errors.append(f"【{h}】必填（非原装来源）")
            loc_label = cell(raw, "存放位置")
            if loc_label:
                loc = loc_by_label.get(loc_label)
                if loc is None:
                    errors.append(f"【存放位置】「{loc_label}」不存在（格式：库房/货位）")
                elif model is not None:
                    allowed = loc.allowed_categories or []
                    if allowed and model.category not in allowed:
                        errors.append(
                            f"【存放位置】「{loc_label}」仅允许：{'/'.join(allowed)}"
                        )
            if group and group not in enums.RESPONSIBLE_GROUPS:
                errors.append(
                    f"【运维部门】「{group}」非法，允许：{' / '.join(enums.RESPONSIBLE_GROUPS)}"
                )
            if supplier and supplier not in supplier_names:
                errors.append(f"【供应商】「{supplier}」不在名录中，请先维护")
            purchase_date = parse_date(cell(raw, "到货验收日期"), errors, "到货验收日期")
            warranty = parse_date(cell(raw, "维保到位时间"), errors, "维保到位时间")

        kwargs = {
            "model_id": model.id if model else None,
            "fixed_asset_no": asset_no,
            "serial_no": serial_no,
            "source_type": source,
            "server_id": server.id if server else None,
            "storage_location_id": loc.id if loc else None,
            "responsible_group": group or None,
            "supplier": supplier or None,
            "contract_no": contract_no or None,
            "project": project or None,
            "owner_unit": owner_unit or None,
            "purchase_date": purchase_date,
            "warranty_expiry": warranty,
            "purchase_amount": amount,
            "allocatable_flag": flag,
            "remark": remark,
        }
        preview = {
            "category": cat,
            "model_name": model_name,
            "fixed_asset_no": asset_no,
            "source_type": source,
            "server_asset_no": cell(raw, "关联服务器"),
            "location": cell(raw, "存放位置"),
        }
        rows.append({"line": line_no, "ok": not errors, "errors": errors, "data": preview, "kwargs": kwargs})

    if not rows:
        raise BusinessError("CSV 中没有数据行")
    valid = sum(1 for r in rows if r["ok"])
    return {"rows": rows, "total": len(rows), "valid": valid}


def batch_import_parts(
    db: Session, content: str, *, operator_id: int, dry_run: bool
) -> dict:
    """两段式导入：dry_run=True 仅校验预览；False 时整批通过才逐件入库。"""
    report = parse_parts_csv(db, content)
    # kwargs 不往外传
    public_rows = [
        {"line": r["line"], "ok": r["ok"], "errors": r["errors"], "data": r["data"]}
        for r in report["rows"]
    ]
    public = {"rows": public_rows, "total": report["total"], "valid": report["valid"]}
    if dry_run:
        return {**public, "created": 0, "committed": False}
    if report["valid"] != report["total"]:
        bad = report["total"] - report["valid"]
        raise BusinessError(f"存在 {bad} 行校验未通过，整批未导入（请修正后重新上传）")

    # 预生成：为未填固定资产编号的行自动生成（同一批次内互不冲突）
    auto_gen_nos: set[str] = set()
    for r in report["rows"]:
        fixed = (r["kwargs"].get("fixed_asset_no") or "").strip()
        if fixed:
            continue
        model_id = r["kwargs"].get("model_id")
        if not model_id:
            continue
        model = db.get(PartModel, model_id)
        if model is None:
            continue
        candidate = parts_service.generate_next_fixed_asset_no(db, model.category)
        while candidate in auto_gen_nos:
            parts = candidate.rsplit("-", 1)
            seq = int(parts[1]) + 1
            candidate = f"{parts[0]}-{seq:03d}"
        auto_gen_nos.add(candidate)
        r["kwargs"]["fixed_asset_no"] = candidate

    created_nos: list[str] = []
    current_line: int | None = None
    try:
        for r in report["rows"]:
            current_line = r["line"]
            part = parts_service.inbound(
                db, operator_id=operator_id, commit=False, **r["kwargs"]
            )
            created_nos.append(part.fixed_asset_no)
        db.commit()
    except BusinessError as e:
        db.rollback()
        where = f"第 {current_line} 行" if current_line is not None else "提交时"
        raise BusinessError(f"{where}入库失败：{e.message}。整批未导入") from e
    except Exception:
        db.rollback()
        raise
    return {**public, "created": len(created_nos), "committed": True}
