from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .database import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class PartModel(Base):
    __tablename__ = "part_model"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pn: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    spec: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    parts: Mapped[list["Part"]] = relationship(back_populates="model")


class Part(Base):
    __tablename__ = "part"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("part_model.id"), nullable=False)
    fixed_asset_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    serial_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    contract_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    purchase_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    purchase_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    responsible_group: Mapped[str] = mapped_column(String(50), nullable=False)
    sensitivity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_no: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    serial_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    room: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rack: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    u_position: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    responsible_group: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    run_status: Mapped[str] = mapped_column(String(50), nullable=False)

    links: Mapped[list["PartServerLink"]] = relationship(back_populates="server")


class StorageLocation(Base):
    __tablename__ = "storage_location"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warehouse: Mapped[str] = mapped_column(String(100), nullable=False)
    slot: Mapped[str] = mapped_column(String(100), nullable=False)


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_info: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


class Approval(Base):
    __tablename__ = "approval"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("part.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    overall_status: Mapped[str] = mapped_column(String(50), nullable=False)
    current_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    expected_return_date: Mapped[date] = mapped_column(Date, nullable=False)
    dest_org_id: Mapped[int] = mapped_column(ForeignKey("external_org.id"), nullable=False)
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
    part_id: Mapped[int] = mapped_column(ForeignKey("part.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stocktake_id: Mapped[int] = mapped_column(ForeignKey("stocktake.id"), nullable=False)
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
