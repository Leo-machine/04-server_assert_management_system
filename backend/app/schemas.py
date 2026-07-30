from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: int
    name: str
    role_label: Optional[str] = None

    model_config = {"from_attributes": True}


class PartModelOut(BaseModel):
    id: int
    category: str
    model_name: str
    brand: Optional[str] = None
    pn: Optional[str] = None
    spec: Optional[dict] = None

    model_config = {"from_attributes": True}


class StorageLocationOut(BaseModel):
    id: int
    warehouse: str
    slot: str

    model_config = {"from_attributes": True}


class ExternalOrgOut(BaseModel):
    id: int
    org_name: str
    contact: Optional[str] = None
    contact_info: Optional[str] = None

    model_config = {"from_attributes": True}


class ServerOut(BaseModel):
    id: int
    asset_no: str
    model: Optional[str] = None
    serial_no: Optional[str] = None
    room: Optional[str] = None
    rack: Optional[str] = None
    u_position: Optional[str] = None
    responsible_group: Optional[str] = None
    run_status: str

    model_config = {"from_attributes": True}


class ServerRunStatusIn(BaseModel):
    run_status: str


class PartOut(BaseModel):
    id: int
    model_id: int
    fixed_asset_no: str
    serial_no: Optional[str] = None
    source_type: str
    contract_no: Optional[str] = None
    purchase_amount: Optional[Decimal] = None
    purchase_date: Optional[date] = None
    responsible_group: str
    sensitivity: Optional[str] = None
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
    remark: Optional[str] = None

    model_config = {"from_attributes": True}


class InboundIn(BaseModel):
    model_id: int
    fixed_asset_no: str
    storage_location_id: int
    source_type: str = "单独合同"
    responsible_group: str = "基础组"
    serial_no: Optional[str] = None
    contract_no: Optional[str] = None
    purchase_amount: Optional[Decimal] = None
    purchase_date: Optional[date] = None
    sensitivity: Optional[str] = None
    remark: Optional[str] = None


class InstallIn(BaseModel):
    server_id: int
    slot: Optional[str] = None
    remark: Optional[str] = None


class UninstallIn(BaseModel):
    storage_location_id: int
    remark: Optional[str] = None


class ReturnIn(BaseModel):
    storage_location_id: int
    remark: Optional[str] = None


class LoanApprovalIn(BaseModel):
    part_id: int
    dest_org_id: int
    expected_return_date: date
    approver_ids: list[int] = Field(..., min_length=3, max_length=3)
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
    expected_return_date: date
    dest_org_id: int
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
