"""业务枚举取值（字符串存库，与设计文档一致）。"""

# 配件状态（demo 用到的子集；七态枚举值仍保留可读性）
STATUS_IN_STOCK = "在库"
STATUS_IN_USE = "在用"
STATUS_LOANED = "借出"
STATUS_DAMAGED = "损坏"
STATUS_IN_TRANSIT = "在途"
STATUS_TRANSFERRED = "已调拨"
STATUS_SCRAPPED = "报废"

# 事件类型（本主线）
EVENT_INBOUND = "入库"
EVENT_INSTALL = "装机"
EVENT_UNINSTALL = "拆下"
EVENT_LOAN = "借出"
EVENT_RETURN = "归还"

# 位置种类
LOC_STORAGE = "库位"
LOC_SERVER = "服务器"
LOC_EXTERNAL = "外单位"
LOC_NONE = "无"

# 服务器运行状态（三值留全；退役无 API）
RUN_NOT_LIVE = "未投运"
RUN_LIVE = "投运"
RUN_RETIRED = "退役"

# 审批
ACTION_LOAN = "借出"
APPROVAL_PENDING = "审批中"
APPROVAL_APPROVED = "通过"
APPROVAL_REJECTED = "驳回"
APPROVAL_WITHDRAWN = "撤回"

STEP_PENDING = "待审"
STEP_APPROVED = "通过"
STEP_REJECTED = "驳回"

# 来源 / 责任组
SOURCE_TYPES = ("随器采购", "单独合同", "维保换新")
RESPONSIBLE_GROUPS = ("基础组", "运营组", "网络组", "平台组")

# 盘点
SCOPE_FULL = "全盘"
SCOPE_KINDS = ("全盘", "按机房", "按责任组", "按配件类型", "指定清单")

STOCKTAKE_IN_PROGRESS = "进行中"
STOCKTAKE_COMPLETED = "已完成"
STOCKTAKE_ARCHIVED = "已归档"

RESULT_PENDING = "待复核"
RESULT_MATCH = "相符"
RESULT_SHORTAGE = "盘亏"
RESULT_SURPLUS = "盘盈"
RESULT_MISPLACE = "错位"

DISC_SHORTAGE = "盘亏"
DISC_SURPLUS = "盘盈"
DISC_MISPLACE = "错位"

DISC_STATUS_HOLD = "挂起追查"
DISC_STATUS_REVIEW = "待复核"
DISC_STATUS_RESOLVED = "已处置"
