from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: int
    username: Optional[str] = None
    name: str
    role_label: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None

    model_config = {"from_attributes": True}


class PartModelOut(BaseModel):
    id: int
    category: str
    model_name: str
    brand: Optional[str] = None
    pn: Optional[str] = None
    spec: Optional[dict] = None
    capacity_gb: Optional[int] = None
    ddr_gen: Optional[str] = None

    model_config = {"from_attributes": True}


class PartModelIn(BaseModel):
    category: str
    model_name: str
    brand: Optional[str] = None
    pn: Optional[str] = None
    spec: Optional[dict] = None


class PartModelUpdateIn(BaseModel):
    category: Optional[str] = None
    model_name: Optional[str] = None
    brand: Optional[str] = None
    pn: Optional[str] = None
    spec: Optional[dict] = None


class CategoryFieldOut(BaseModel):
    key: str
    label: str
    type: str
    required: bool = False
    strict: bool = False
    options: Optional[list[str]] = None
    unit: Optional[str] = None
    placeholder: Optional[str] = None


class CategorySchemaOut(BaseModel):
    category: str
    fields: list[CategoryFieldOut]


class StorageLocationOut(BaseModel):
    id: int
    warehouse: str
    slot: str
    location_type: Optional[str] = None
    allowed_categories: Optional[list] = None
    part_count: Optional[int] = None

    model_config = {"from_attributes": True}


class StorageLocationIn(BaseModel):
    warehouse: str
    slot: str
    location_type: Optional[str] = None
    allowed_categories: Optional[list] = None


class StorageLocationUpdateIn(BaseModel):
    warehouse: Optional[str] = None
    slot: Optional[str] = None
    location_type: Optional[str] = None
    allowed_categories: Optional[list] = None


class LocationDistributionOut(BaseModel):
    id: int
    warehouse: str
    slot: str
    location_type: Optional[str] = None
    allowed_categories: Optional[list] = None
    part_count: int
    parts_by_status: dict = {}


class ExternalOrgOut(BaseModel):
    id: int
    org_name: str
    contact: Optional[str] = None
    contact_info: Optional[str] = None

    model_config = {"from_attributes": True}


class ServerOut(BaseModel):
    id: int
    asset_no: str
    model: str
    serial_no: str
    location_id: int
    responsible_group: str
    run_status: str
    supplier: str
    contract_no: str
    project: str
    owner_unit: str
    warranty_expiry: date
    arrival_date: date
    purchase_amount: Decimal
    disk_slot_count: Optional[int] = None
    disk_interface: Optional[str] = None
    mem_slot_count: Optional[int] = None
    mem_ddr_gens: Optional[str] = None
    pcie_slot_count: Optional[int] = None
    nvme_slot_count: Optional[int] = None
    nvme_interface: Optional[str] = None

    model_config = {"from_attributes": True}


class ServerIn(BaseModel):
    asset_no: str
    model: str
    serial_no: str
    location_id: int
    responsible_group: str = "基础组"
    run_status: str = "未投运"
    supplier: str
    contract_no: str
    project: str
    owner_unit: str = "本单位信息中心"
    warranty_expiry: date
    arrival_date: date
    purchase_amount: Decimal
    disk_slot_count: Optional[int] = None
    disk_interface: Optional[str] = None
    mem_slot_count: Optional[int] = None
    mem_ddr_gens: Optional[str] = None
    pcie_slot_count: Optional[int] = None
    nvme_slot_count: Optional[int] = None
    nvme_interface: Optional[str] = None


class ServerUpdateIn(BaseModel):
    asset_no: Optional[str] = None
    model: Optional[str] = None
    serial_no: Optional[str] = None
    location_id: Optional[int] = None
    responsible_group: Optional[str] = None
    supplier: Optional[str] = None
    contract_no: Optional[str] = None
    project: Optional[str] = None
    owner_unit: Optional[str] = None
    warranty_expiry: Optional[date] = None
    arrival_date: Optional[date] = None
    purchase_amount: Optional[Decimal] = None
    disk_slot_count: Optional[int] = None
    disk_interface: Optional[str] = None
    mem_slot_count: Optional[int] = None
    mem_ddr_gens: Optional[str] = None
    pcie_slot_count: Optional[int] = None
    nvme_slot_count: Optional[int] = None
    nvme_interface: Optional[str] = None

    model_config = {"from_attributes": True}


class ServerInstalledPartOut(BaseModel):
    id: int
    fixed_asset_no: str
    serial_no: Optional[str] = None
    category: Optional[str] = None
    model_name: Optional[str] = None
    brand: Optional[str] = None
    current_status: str
    slot: Optional[str] = None
    allocatable_flag: Optional[str] = None
    source_type: Optional[str] = None


class ServerDetailOut(ServerOut):
    installed_parts: list[ServerInstalledPartOut] = []
    installed_count: int = 0
    installed_by_category: dict[str, int] = {}


class ServerRunStatusIn(BaseModel):
    run_status: str
    work_order_no: str  # 工作票工单号，必填


class ServerMovementOut(BaseModel):
    id: int
    server_id: int
    event_type: str
    run_status_from: Optional[str] = None
    run_status_to: str
    occurred_at: datetime
    operator_id: int
    work_order_no: Optional[str] = None
    remark: Optional[str] = None

    model_config = {"from_attributes": True}


class PartOut(BaseModel):
    id: int
    model_id: int
    fixed_asset_no: str
    serial_no: Optional[str] = None
    source_type: str
    contract_no: Optional[str] = None
    purchase_amount: Optional[Decimal] = None
    purchase_date: Optional[date] = None
    responsible_group: str  # 运维部门（列名保持不动）
    sensitivity: Optional[str] = None
    supplier: Optional[str] = None
    project: Optional[str] = None
    owner_unit: str
    warranty_expiry: Optional[date] = None
    allocatable_flag: str
    current_status: str
    current_loc_kind: Optional[str] = None
    current_loc_id: Optional[int] = None
    is_overdue: bool = False
    model: Optional[PartModelOut] = None

    model_config = {"from_attributes": True}


class MovementOut(BaseModel):
    id: int
    part_id: int
    event_type: str
    status_from: Optional[str] = None
    status_to: str
    occurred_at: datetime
    operator_id: int
    loc_from_kind: Optional[str] = None
    loc_from_id: Optional[int] = None
    loc_to_kind: Optional[str] = None
    loc_to_id: Optional[int] = None
    work_order_no: Optional[str] = None
    approval_id: Optional[int] = None
    expected_return_date: Optional[date] = None
    reason_code: Optional[str] = None
    event_group_id: Optional[str] = None
    remark: Optional[str] = None

    model_config = {"from_attributes": True}


class InboundIn(BaseModel):
    model_id: int
    fixed_asset_no: str = ""  # 空串 = 系统自动生成品类前缀-日期-序号
    source_type: str
    serial_no: str
    purchase_amount: Decimal
    allocatable_flag: str
    remark: str
    # 独立合同采购/框招正偏移：必填（服务端校验）
    storage_location_id: Optional[int] = None
    responsible_group: Optional[str] = None  # 运维部门
    contract_no: Optional[str] = None
    purchase_date: Optional[date] = None
    supplier: Optional[str] = None
    project: Optional[str] = None
    owner_unit: Optional[str] = None
    warranty_expiry: Optional[date] = None
    # 服务器原装：必填（服务端校验），其余合同字段由服务器档案带出
    server_id: Optional[int] = None
    # 敏感标记已从表单去除；列保留兼容，默认「无」
    sensitivity: Optional[str] = None


class PartPublicUpdateIn(BaseModel):
    supplier: Optional[str] = None
    project: Optional[str] = None
    owner_unit: Optional[str] = None
    warranty_expiry: Optional[date] = None
    clear_warranty: bool = False
    allocatable_flag: Optional[str] = None


class AllocatableSummaryItem(BaseModel):
    category: str
    capacity_gb: Optional[int] = None
    ddr_gen: Optional[str] = None
    spec_label: str
    allocatable_count: int
    home_owner_unit: str


class InstallIn(BaseModel):
    server_id: int
    slot: Optional[str] = None
    remark: Optional[str] = None


class UninstallIn(BaseModel):
    storage_location_id: int
    damaged: bool = False  # True = 坏件拆下（在用→损坏）
    remark: Optional[str] = None


class DamageIn(BaseModel):
    remark: str  # 必填，说明损坏情况


class ReturnIn(BaseModel):
    storage_location_id: int
    remark: Optional[str] = None


class LoanApprovalIn(BaseModel):
    part_id: int
    dest_org_id: int
    expected_return_date: date
    approver_ids: list[int] = Field(..., min_length=3, max_length=3)
    remark: Optional[str] = None


class TransferApprovalIn(BaseModel):
    part_id: int
    dest_org_id: int
    approver_ids: list[int] = Field(..., min_length=3, max_length=3)
    reason_code: Optional[str] = None
    remark: Optional[str] = None


class ScrapApprovalIn(BaseModel):
    part_id: int
    reason_code: str
    approver_ids: list[int] = Field(..., min_length=3, max_length=3)
    attachment_ref: Optional[str] = None
    remark: Optional[str] = None


class DecideIn(BaseModel):
    level: int
    approve: bool
    opinion: Optional[str] = None


class ApprovalStepOut(BaseModel):
    id: int
    level: int
    approver_id: int
    step_status: str
    opinion: Optional[str] = None
    decided_at: Optional[datetime] = None
    approver: Optional[UserOut] = None

    model_config = {"from_attributes": True}


class ApprovalOut(BaseModel):
    id: int
    part_id: int
    action_type: str
    applicant_id: int
    applied_at: datetime
    overall_status: str
    current_level: int
    expected_return_date: Optional[date] = None
    dest_org_id: Optional[int] = None
    reason_code: Optional[str] = None
    attachment_ref: Optional[str] = None
    remark: Optional[str] = None
    steps: list[ApprovalStepOut] = []
    applicant: Optional[UserOut] = None
    dest_org: Optional[ExternalOrgOut] = None

    model_config = {"from_attributes": True}


class ReplayOut(BaseModel):
    current_status: Optional[str] = None
    current_loc_kind: Optional[str] = None
    current_loc_id: Optional[int] = None
    matches_cache: bool


# ----- 盘点 -----
class StocktakeCreateIn(BaseModel):
    scope_kind: str = "全盘"
    scope_value: Optional[dict] = None


class StocktakeCheckIn(BaseModel):
    scanned_asset_no: Optional[str] = None
    item_id: Optional[int] = None
    actual_loc_kind: Optional[str] = None
    actual_loc_id: Optional[int] = None
    missing: bool = False


class StocktakeConfirmExternalIn(BaseModel):
    item_id: int
    present: bool
    feedback_source: str


class StocktakeDiscrepancyOut(BaseModel):
    id: int
    stocktake_item_id: int
    discrepancy_type: str
    status: str
    reviewer_id: Optional[int] = None
    review_conclusion: Optional[str] = None
    resolution: Optional[str] = None
    linked_ref: Optional[str] = None

    model_config = {"from_attributes": True}


class StocktakeItemOut(BaseModel):
    id: int
    stocktake_id: int
    part_id: Optional[int] = None
    expected_loc_kind: Optional[str] = None
    expected_loc_id: Optional[int] = None
    expected_status_derived: Optional[str] = None  # 仅展示
    result: str
    actual_loc_kind: Optional[str] = None
    actual_loc_id: Optional[int] = None
    scanned_asset_no: Optional[str] = None
    checker_id: Optional[int] = None
    checked_at: Optional[datetime] = None
    feedback_source: Optional[str] = None
    requires_external_confirm: bool = False
    fixed_asset_no: Optional[str] = None
    discrepancy: Optional[StocktakeDiscrepancyOut] = None

    model_config = {"from_attributes": True}


class StocktakeOut(BaseModel):
    id: int
    scope_kind: str
    scope_value: Optional[dict] = None
    initiator_id: int
    initiated_at: datetime
    snapshot_at: datetime
    status: str
    summary: dict = {}
    items: list[StocktakeItemOut] = []

    model_config = {"from_attributes": True}


class StocktakeListOut(BaseModel):
    id: int
    scope_kind: str
    initiator_id: int
    initiated_at: datetime
    snapshot_at: datetime
    status: str

    model_config = {"from_attributes": True}


# ----- 品牌 -----
class BrandOut(BaseModel):
    id: int
    name: str
    categories: Optional[list[str]] = None

    model_config = {"from_attributes": True}


class BrandIn(BaseModel):
    name: str
    categories: Optional[list[str]] = None


class BrandUpdateIn(BaseModel):
    name: Optional[str] = None
    categories: Optional[list[str]] = None


# ----- 供应商 -----
class SupplierOut(BaseModel):
    id: int
    name: str
    contact: Optional[str] = None
    contact_info: Optional[str] = None
    remark: Optional[str] = None

    model_config = {"from_attributes": True}


class SupplierIn(BaseModel):
    name: str
    contact: Optional[str] = None
    contact_info: Optional[str] = None
    remark: Optional[str] = None


class SupplierUpdateIn(BaseModel):
    name: Optional[str] = None
    contact: Optional[str] = None
    contact_info: Optional[str] = None
    remark: Optional[str] = None
