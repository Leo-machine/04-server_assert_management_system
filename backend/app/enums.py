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
EVENT_TRANSFER = "调拨"
EVENT_SCRAP = "报废"
# 第 8 种原子事件：盘点错位后的说明性校正履历（状态不变，仅位置修正）
EVENT_CORRECT = "校正"

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
ACTION_TRANSFER = "调拨"
ACTION_SCRAP = "报废"
ACTION_TYPES = (ACTION_LOAN, ACTION_TRANSFER, ACTION_SCRAP)
APPROVAL_PENDING = "审批中"
APPROVAL_APPROVED = "通过"
APPROVAL_REJECTED = "驳回"
APPROVAL_WITHDRAWN = "撤回"

# 报废/调拨缘由
REASON_SCRAP_DESTROY = "本单位销毁"
REASON_SCRAP_FACTORY = "返厂换新"
REASON_CODES_SCRAP = (REASON_SCRAP_DESTROY, REASON_SCRAP_FACTORY)

STEP_PENDING = "待审"
STEP_APPROVED = "通过"
STEP_REJECTED = "驳回"

# 来源 / 责任组（responsible_group = 运维部门，列名保持不动）
SOURCE_ORIGINAL = "服务器原装"
SOURCE_CONTRACT = "独立合同采购"
SOURCE_FRAMEWORK = "框招正偏移"
SOURCE_TYPES = (SOURCE_ORIGINAL, SOURCE_CONTRACT, SOURCE_FRAMEWORK)
RESPONSIBLE_GROUPS = ("基础组", "运营组", "网络组", "平台组")

# 报废影像证据强制：按配件类型判断（算力卡类高值件）
SCRAP_ATTACHMENT_CATEGORIES = ("算力卡",)

# 可调配标记（实物公共字段）
ALLOC_GENERAL = "通用可调"
ALLOC_RESERVED = "保留"
ALLOCATABLE_FLAGS = (ALLOC_GENERAL, ALLOC_RESERVED)

# demo：本单位产权标识（与 part.owner_unit 比对）
HOME_OWNER_UNIT = "本单位信息中心"

# 内存代际
DDR_GENS = ("DDR4", "DDR5")

# 用户角色（轻量权限：服务端硬校验，选人切换仍保留）
ROLE_OPERATOR = "操作员"
ROLE_APPROVER = "审批人"
ROLE_ADMIN = "管理员"
ROLES = (ROLE_OPERATOR, ROLE_APPROVER, ROLE_ADMIN)
# 可担任审批人 / 盘点管理的角色
APPROVER_ROLES = (ROLE_APPROVER, ROLE_ADMIN)

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
