from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .database import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 登录账号（唯一；早期版本用 name 登录，迁移时由 name 回填）
    username: Mapped[Optional[str]] = mapped_column(
        String(50), unique=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # 业务角色：设备供应商 / 外委运维 / 主业运维 / 领导
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="主业运维")
    password_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # 账号状态：正常 / 待审核（自助注册）/ 驳回 / 停用
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="正常")
    # 自助注册申请信息
    applied_role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    apply_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    reject_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class PartModel(Base):
    __tablename__ = "part_model"
    __table_args__ = (
        UniqueConstraint("category", "model_name", name="uq_part_model_cat_name"),
        Index("ix_part_model_mem_agg", "category", "capacity_gb", "ddr_gen"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pn: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    spec: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # 内存可聚合正式列（方案甲）；其它类型保持 NULL。与 spec 双写。
    capacity_gb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ddr_gen: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    asset_category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("asset_category.id"), nullable=True
    )

    parts: Mapped[list["Part"]] = relationship(back_populates="model")


class AssetCategory(Base):
    """可扩展的三级资产目录。

    business_category 用于将三级目录映射到已落地的配件品类；
    留空表示目录已建档，但业务录入能力尚未接入。
    """

    __tablename__ = "asset_category"
    __table_args__ = (
        UniqueConstraint("parent_id", "name", name="uq_asset_category_parent_name"),
        UniqueConstraint("business_category", name="uq_asset_category_business"),
        Index("ix_asset_category_parent_sort", "parent_id", "sort_order", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("asset_category.id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    business_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class Part(Base):
    __tablename__ = "part"
    __table_args__ = (
        Index(
            "ix_part_allocatable",
            "current_status",
            "owner_unit",
            "allocatable_flag",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("part_model.id"), nullable=False)
    fixed_asset_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    serial_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    contract_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    purchase_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    purchase_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # responsible_group = 运维部门（列名保持不动，等同「运维部门」）
    responsible_group: Mapped[str] = mapped_column(String(50), nullable=False)
    sensitivity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # 七类通用公共字段（Demo 03）
    supplier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    project: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    owner_unit: Mapped[str] = mapped_column(String(100), nullable=False, default="本单位信息中心")
    warranty_expiry: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    allocatable_flag: Mapped[str] = mapped_column(
        String(20), nullable=False, default="通用可调"
    )
    # 投影缓存；真相在 movement_log
    current_status: Mapped[str] = mapped_column(String(50), nullable=False)
    current_loc_kind: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    current_loc_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    model: Mapped["PartModel"] = relationship(back_populates="parts")
    movements: Mapped[list["MovementLog"]] = relationship(back_populates="part")
    server_link: Mapped[Optional["PartServerLink"]] = relationship(
        back_populates="part", uselist=False
    )


class Server(Base):
    __tablename__ = "server"
    __table_args__ = (
        UniqueConstraint("asset_no", name="uq_server_asset_no"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_no: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    serial_no: Mapped[str] = mapped_column(String(100), nullable=False)
    # 部署位置（引用存放位置模块）
    location_id: Mapped[int] = mapped_column(ForeignKey("storage_location.id"), nullable=False)
    responsible_group: Mapped[str] = mapped_column(String(50), nullable=False)
    run_status: Mapped[str] = mapped_column(String(50), nullable=False)
    # 合同/采购信息
    supplier: Mapped[str] = mapped_column(String(100), nullable=False)
    contract_no: Mapped[str] = mapped_column(String(100), nullable=False)
    project: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_unit: Mapped[str] = mapped_column(String(100), nullable=False)
    warranty_expiry: Mapped[date] = mapped_column(Date, nullable=False)
    arrival_date: Mapped[date] = mapped_column(Date, nullable=False)
    purchase_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # 机箱插槽规格（建档时维护，供装机容量对照）
    disk_slot_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    disk_interface: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mem_slot_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mem_ddr_gens: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pcie_slot_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    nvme_slot_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    nvme_interface: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    location: Mapped["StorageLocation"] = relationship(foreign_keys=[location_id])

    links: Mapped[list["PartServerLink"]] = relationship(back_populates="server")
    movements: Mapped[list["ServerMovementLog"]] = relationship(back_populates="server")


class StorageLocation(Base):
    __tablename__ = "storage_location"
    __table_args__ = (
        UniqueConstraint("warehouse", "slot", name="uq_storage_warehouse_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warehouse: Mapped[str] = mapped_column(String(100), nullable=False)
    slot: Mapped[str] = mapped_column(String(100), nullable=False)
    location_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    allowed_categories: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)


class PartServerLink(Base):
    __tablename__ = "part_server_link"
    __table_args__ = (UniqueConstraint("part_id", name="uq_part_server_link_part"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("part.id"), nullable=False)
    server_id: Mapped[int] = mapped_column(ForeignKey("server.id"), nullable=False)
    slot: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    part: Mapped["Part"] = relationship(back_populates="server_link")
    server: Mapped["Server"] = relationship(back_populates="links")


class ExternalOrg(Base):
    __tablename__ = "external_org"
    __table_args__ = (
        UniqueConstraint("org_name", name="uq_external_org_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_info: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


class Brand(Base):
    __tablename__ = "brand"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # 适用配件类型（八类子集）。空列表/null = 通用，各类型可选。
    categories: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    asset_category_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)


class Supplier(Base):
    """供应商名录；配件 Part.supplier 存名称字符串（与品牌同模式）。"""

    __tablename__ = "supplier"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    contact: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_info: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    asset_category_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)


class Approval(Base):
    __tablename__ = "approval"
    __table_args__ = (
        Index(
            "uq_approval_pending_part",
            "part_id",
            unique=True,
            sqlite_where=text("overall_status = '审批中'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("part.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    overall_status: Mapped[str] = mapped_column(String(50), nullable=False)
    current_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 仅借出必填；调拨/报废无归还日
    expected_return_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # 借出/调拨必填；报废不需要
    dest_org_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("external_org.id"), nullable=True
    )
    # 报废必填（本单位销毁/返厂换新）；调拨可选（划转依据等）
    reason_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # 高值件报废影像证据引用（一期存引用串，文件上传后续做）
    attachment_ref: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    steps: Mapped[list["ApprovalStep"]] = relationship(
        back_populates="approval", order_by="ApprovalStep.level"
    )
    part: Mapped["Part"] = relationship()
    applicant: Mapped["User"] = relationship(foreign_keys=[applicant_id])
    dest_org: Mapped["ExternalOrg"] = relationship()


class ApprovalStep(Base):
    __tablename__ = "approval_step"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approval_id: Mapped[int] = mapped_column(ForeignKey("approval.id"), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    step_status: Mapped[str] = mapped_column(String(50), nullable=False)
    opinion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    approval: Mapped["Approval"] = relationship(back_populates="steps")
    approver: Mapped["User"] = relationship(foreign_keys=[approver_id])


class MovementLog(Base):
    """履历表：只允许 INSERT，代码层不得暴露 UPDATE / DELETE。"""

    __tablename__ = "movement_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("part.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status_from: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status_to: Mapped[str] = mapped_column(String(50), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    operator_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    loc_from_kind: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    loc_from_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    loc_to_kind: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    loc_to_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    work_order_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approval_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("approval.id"), nullable=True
    )
    expected_return_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # 报废腿记录销毁方式（本单位销毁/返厂换新）
    reason_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # 换新成对事件绑定（旧件报废 + 新件入库同组；后续波次启用）
    event_group_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    part: Mapped["Part"] = relationship(back_populates="movements")
    operator: Mapped["User"] = relationship(foreign_keys=[operator_id])


class Stocktake(Base):
    __tablename__ = "stocktake"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    initiator_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    initiated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    items: Mapped[list["StocktakeItem"]] = relationship(
        back_populates="stocktake", order_by="StocktakeItem.id"
    )
    initiator: Mapped["User"] = relationship(foreign_keys=[initiator_id])


class StocktakeItem(Base):
    __tablename__ = "stocktake_item"
    __table_args__ = (
        UniqueConstraint("stocktake_id", "part_id", name="uq_stocktake_item_part"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stocktake_id: Mapped[int] = mapped_column(ForeignKey("stocktake.id"), nullable=False, index=True)
    part_id: Mapped[Optional[int]] = mapped_column(ForeignKey("part.id"), nullable=True)
    expected_loc_kind: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    expected_loc_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    result: Mapped[str] = mapped_column(String(50), nullable=False)
    actual_loc_kind: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    actual_loc_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scanned_asset_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    checker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    feedback_source: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    stocktake: Mapped["Stocktake"] = relationship(back_populates="items")
    part: Mapped[Optional["Part"]] = relationship()
    checker: Mapped[Optional["User"]] = relationship(foreign_keys=[checker_id])
    discrepancy: Mapped[Optional["StocktakeDiscrepancy"]] = relationship(
        back_populates="item", uselist=False
    )


class ServerMovementLog(Base):
    """服务器履历：记录运行状态变更事件（仅 INSERT，不 UPDATE/DELETE）。"""

    __tablename__ = "server_movement_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("server.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    run_status_from: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    run_status_to: Mapped[str] = mapped_column(String(50), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    operator_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    work_order_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    server: Mapped["Server"] = relationship(back_populates="movements")
    operator: Mapped["User"] = relationship(foreign_keys=[operator_id])


class StocktakeDiscrepancy(Base):
    __tablename__ = "stocktake_discrepancy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stocktake_item_id: Mapped[int] = mapped_column(
        ForeignKey("stocktake_item.id"), nullable=False, unique=True
    )
    discrepancy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    review_conclusion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    linked_ref: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    item: Mapped["StocktakeItem"] = relationship(back_populates="discrepancy")
