"""八类配件的规格字段定义（单一真相源，供校验与前端渲染）。"""

from typing import Any, Optional


class SpecValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# 用户要求的八类（RAID 与 HBA 分开；算力卡对应原 GPU）
PART_CATEGORIES = (
    "内存",
    "机械硬盘",
    "固态硬盘",
    "RAID卡",
    "光模块",
    "网卡",
    "HBA卡",
    "算力卡",
)

# 服务器整机：只在型号/品牌目录中管理（供服务器建档引用），不走配件入库
SERVER_CATEGORY = "服务器"
ALL_MANAGED_CATEGORIES = PART_CATEGORIES + (SERVER_CATEGORY,)

# 固定资产编号前缀（按品类自动生成：PREFIX-YYYYMMDD-NNN）
CATEGORY_ASSET_PREFIX: dict[str, str] = {
    "内存": "MEM",
    "机械硬盘": "HDD",
    "固态硬盘": "SSD",
    "RAID卡": "RAID",
    "光模块": "OPT",
    "网卡": "NIC",
    "HBA卡": "HBA",
    "算力卡": "GPU",
}

# key: 字段名；type: number|string|enum；required；options 用于 enum；unit 仅展示
# strict: True 表示必须从 options 中取值（驱动聚合列/正式列的字段），
#         缺省为 False 表示 options 仅建议值、接受自定义输入
CATEGORY_SPEC_FIELDS: dict[str, list[dict[str, Any]]] = {
    "内存": [
        {"key": "容量GB", "label": "容量", "type": "number", "required": True, "unit": "GB"},
        {
            "key": "内存类型",
            "label": "代际",
            "type": "enum",
            "required": True,
            "strict": True,
            "options": ["DDR4", "DDR5"],
        },
        {"key": "频率MHz", "label": "频率", "type": "number", "required": False, "unit": "MHz"},
    ],
    "机械硬盘": [
        {"key": "容量TB", "label": "容量", "type": "number", "required": True, "unit": "TB"},
        {
            "key": "接口",
            "label": "接口",
            "type": "enum",
            "required": True,
            "strict": True,
            "options": ["SATA", "SAS"],
        },
        {
            "key": "转速",
            "label": "转速",
            "type": "enum",
            "required": False,
            "options": ["7200", "10000", "15000"],
        },
    ],
    "固态硬盘": [
        {"key": "容量GB", "label": "容量", "type": "number", "required": True, "unit": "GB"},
        {
            "key": "接口协议",
            "label": "接口协议",
            "type": "enum",
            "required": True,
            "strict": True,
            "options": ["SATA", "SAS", "NVMe"],
        },
        {
            "key": "形态",
            "label": "形态",
            "type": "enum",
            "required": False,
            "options": ["2.5寸", "M.2", "U.2", "AIC"],
        },
    ],
    "RAID卡": [
        {"key": "通道数", "label": "通道数", "type": "number", "required": True},
        {"key": "缓存MB", "label": "缓存", "type": "number", "required": False, "unit": "MB"},
        {
            "key": "支持RAID级别",
            "label": "支持 RAID 级别",
            "type": "string",
            "required": False,
            "placeholder": "如 0/1/5/6/10",
        },
    ],
    "光模块": [
        {
            "key": "速率",
            "label": "速率",
            "type": "enum",
            "required": True,
            "strict": True,
            "options": ["1G", "10G", "25G", "40G", "100G", "200G", "400G"],
        },
        {
            "key": "类型",
            "label": "模块类型",
            "type": "enum",
            "required": True,
            "strict": True,
            "options": ["多模SR", "单模LR", "DAC", "AOC"],
        },
        {
            "key": "厂商兼容",
            "label": "厂商兼容",
            "type": "enum",
            "required": True,
            "strict": True,
            "options": ["通用", "华为", "思科", "H3C"],
        },
    ],
    "网卡": [
        {
            "key": "速率",
            "label": "速率",
            "type": "enum",
            "required": True,
            "strict": True,
            "options": ["1G", "10G", "25G", "40G", "100G"],
        },
        {
            "key": "口型",
            "label": "口型",
            "type": "enum",
            "required": True,
            "strict": True,
            "options": ["电口", "光口"],
        },
        {"key": "端口数", "label": "端口数", "type": "number", "required": True},
    ],
    "HBA卡": [
        {
            "key": "子类型",
            "label": "子类型",
            "type": "enum",
            "required": True,
            "strict": True,
            "options": ["SAS-HBA", "FC-HBA"],
        },
        {
            "key": "速率",
            "label": "速率",
            "type": "enum",
            "required": True,
            "strict": True,
            "options": ["8G", "16G", "32G", "12G-SAS", "24G-SAS"],
        },
        {"key": "端口数", "label": "端口数", "type": "number", "required": True},
    ],
    "算力卡": [
        {"key": "显存GB", "label": "显存", "type": "number", "required": True, "unit": "GB"},
        {
            "key": "封装",
            "label": "封装",
            "type": "enum",
            "required": True,
            "strict": True,
            "options": ["PCIe", "SXM"],
        },
        {
            "key": "架构",
            "label": "架构/系列",
            "type": "string",
            "required": False,
            "placeholder": "如 Ampere / Hopper",
        },
    ],
    "服务器": [
        {"key": "机型高度U", "label": "机型高度", "type": "number", "required": True, "unit": "U"},
        {"key": "CPU型号", "label": "CPU 型号", "type": "string", "required": False, "placeholder": "如 Kunpeng 920 / Xeon Gold 6430"},
        {"key": "CPU颗数", "label": "CPU 颗数", "type": "number", "required": False},
        {"key": "内存插槽数", "label": "内存插槽数", "type": "number", "required": False},
        {"key": "盘位数", "label": "盘位数", "type": "number", "required": False},
        {"key": "电源功率W", "label": "电源功率", "type": "number", "required": False, "unit": "W"},
    ],
}


def categories_schema() -> list[dict[str, Any]]:
    return [
        {"category": cat, "fields": CATEGORY_SPEC_FIELDS[cat]}
        for cat in ALL_MANAGED_CATEGORIES
    ]


def validate_category(category: str) -> None:
    if category not in ALL_MANAGED_CATEGORIES:
        raise SpecValidationError(
            f"非法配件类型「{category}」，允许：{' / '.join(ALL_MANAGED_CATEGORIES)}"
        )


def validate_and_normalize_spec(category: str, spec: Optional[dict]) -> dict:
    """按类型校验并规范化 spec；必填缺失则报错。"""
    validate_category(category)
    fields = CATEGORY_SPEC_FIELDS[category]
    raw = dict(spec or {})
    cleaned: dict[str, Any] = {}

    for field in fields:
        key = field["key"]
        label = field["label"]
        val = raw.get(key)
        if val is None or val == "":
            if field.get("required"):
                raise SpecValidationError(
                    f"「{category}」规格缺少必填字段：{label}（{key}）"
                )
            continue

        ftype = field["type"]
        if ftype == "number":
            try:
                num = float(val)
            except (TypeError, ValueError) as e:
                raise SpecValidationError(f"「{label}」须为数字") from e
            if num <= 0:
                raise SpecValidationError(f"「{label}」须大于 0")
            cleaned[key] = int(num) if num == int(num) else num
        elif ftype == "enum":
            options = field.get("options") or []
            strict = field.get("strict", False)
            sval = str(val).strip()
            if not sval:
                if field.get("required"):
                    raise SpecValidationError(f"「{category}」规格缺少必填字段：{label}")
                continue
            # strict: 必须从 options 中取值（驱动聚合/正式列）
            if strict and sval not in options:
                raise SpecValidationError(
                    f"「{label}」取值非法：{sval}，允许：{' / '.join(options)}"
                )
            cleaned[key] = sval
        else:
            cleaned[key] = str(val).strip()
            if not cleaned[key] and field.get("required"):
                raise SpecValidationError(f"「{category}」规格缺少必填字段：{label}")

    return cleaned
