"""CSV 文本与日期解析共用工具。"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Optional


def csv_text(rows: list[list[str]]) -> str:
    """UTF-8 BOM，Excel/WPS 直接打开不乱码。"""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    for r in rows:
        w.writerow(r)
    return "﻿" + buf.getvalue()


def parse_date(val: str, errors: list[str], header: str) -> Optional[date]:
    """接受 YYYY-MM-DD 与 Excel/WPS 常见的 YYYY/M/D、YYYY.M.D。"""
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    errors.append(f"【{header}】「{val}」须为日期（如 2026-08-01）")
    return None
