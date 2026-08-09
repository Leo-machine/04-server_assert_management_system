"""针对代码审查发现问题的回归测试。"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import enums
from app.models import Approval, Part, PartModel, Server, StorageLocation, Supplier
from app.services import parts as parts_service
from app.services.movement import BusinessError


def _memory_model(db_session) -> PartModel:
    return db_session.scalars(
        select(PartModel).where(PartModel.category == "内存")
    ).first()


def _compatible_location(db_session, category: str) -> StorageLocation:
    for loc in db_session.scalars(select(StorageLocation)).all():
        if not loc.allowed_categories or category in loc.allowed_categories:
            return loc
    raise AssertionError("种子数据应包含兼容库位")


def _restricted_location(db_session) -> StorageLocation:
    loc = StorageLocation(
        warehouse="回归测试库",
        slot="GPU-ONLY",
        location_type="库房货架",
        allowed_categories=["算力卡"],
    )
    db_session.add(loc)
    db_session.commit()
    return loc


def test_auto_asset_number_retries_when_first_flush_conflicts(db_session, monkeypatch):
    model = _memory_model(db_session)
    loc = _compatible_location(db_session, model.category)
    supplier = db_session.scalars(select(Supplier)).first()
    real_flush = db_session.flush
    calls = 0

    def conflict_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise IntegrityError(
                "INSERT INTO part ...",
                {},
                Exception("UNIQUE constraint failed: part.fixed_asset_no"),
            )
        return real_flush(*args, **kwargs)

    monkeypatch.setattr(db_session, "flush", conflict_once)
    part = parts_service.inbound(
        db_session,
        operator_id=1,
        model_id=model.id,
        source_type=enums.SOURCE_CONTRACT,
        storage_location_id=loc.id,
        responsible_group=enums.RESPONSIBLE_GROUPS[0],
        serial_no="SN-RETRY-001",
        contract_no="HT-RETRY-001",
        purchase_amount=Decimal("100.00"),
        purchase_date=datetime.now().date(),
        supplier=supplier.name,
        project="并发重试",
        owner_unit=enums.HOME_OWNER_UNIT,
        warranty_expiry=datetime.now().date(),
        allocatable_flag=enums.ALLOC_GENERAL,
        remark="测试首次唯一键冲突",
    )

    assert calls >= 3  # 第一次冲突 + Part flush + MovementLog flush
    assert part.fixed_asset_no
    assert len(part.movements) == 1


def test_database_rejects_two_pending_approvals_for_same_part(db_session):
    part = db_session.scalars(
        select(Part).where(Part.current_status == enums.STATUS_IN_STOCK)
    ).first()
    base = {
        "part_id": part.id,
        "action_type": enums.ACTION_SCRAP,
        "applicant_id": 1,
        "applied_at": datetime.now(timezone.utc),
        "overall_status": enums.APPROVAL_PENDING,
        "current_level": 1,
    }
    db_session.add(Approval(**base))
    db_session.commit()
    db_session.add(Approval(**base))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_return_rejects_location_category_mismatch(db_session):
    part = db_session.scalars(
        select(Part)
        .join(Part.model)
        .where(
            PartModel.category == "内存",
            Part.current_status == enums.STATUS_IN_STOCK,
        )
    ).first()
    restricted = _restricted_location(db_session)
    part.current_status = enums.STATUS_LOANED
    part.current_loc_kind = enums.LOC_EXTERNAL
    part.current_loc_id = 1
    db_session.commit()

    with pytest.raises(BusinessError, match="仅允许"):
        parts_service.return_from_loan(
            db_session,
            part_id=part.id,
            operator_id=1,
            storage_location_id=restricted.id,
        )


def test_uninstall_rejects_location_category_mismatch(db_session):
    part = db_session.scalars(
        select(Part)
        .join(Part.model)
        .where(
            PartModel.category == "内存",
            Part.current_status == enums.STATUS_IN_STOCK,
        )
    ).first()
    server = db_session.scalars(
        select(Server).where(Server.run_status == enums.RUN_NOT_LIVE)
    ).first()
    restricted = _restricted_location(db_session)
    parts_service.install(
        db_session,
        part_id=part.id,
        operator_id=1,
        server_id=server.id,
    )

    with pytest.raises(BusinessError, match="仅允许"):
        parts_service.uninstall(
            db_session,
            part_id=part.id,
            operator_id=1,
            storage_location_id=restricted.id,
        )
