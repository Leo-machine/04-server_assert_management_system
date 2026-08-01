"""盘点发现层：只登记差异，绝不写履历、不改 part 投影。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .. import enums
from ..models import (
    ExternalOrg,
    Part,
    Server,
    Stocktake,
    StocktakeDiscrepancy,
    StocktakeItem,
    StorageLocation,
    User,
)
from .movement import BusinessError

# 红线：本模块只允许从 movement 导入 BusinessError；禁止导入任何写履历/改投影符号。


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def derived_status_from_loc(loc_kind: Optional[str]) -> Optional[str]:
    """仅用于展示的只读投影，禁止参与判定。"""
    if loc_kind == enums.LOC_STORAGE:
        return enums.STATUS_IN_STOCK
    if loc_kind == enums.LOC_SERVER:
        return enums.STATUS_IN_USE
    if loc_kind == enums.LOC_EXTERNAL:
        return enums.STATUS_LOANED
    return None


def _require_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise BusinessError(f"操作人不存在: {user_id}")
    return user


def _get_stocktake(db: Session, stocktake_id: int) -> Stocktake:
    st = db.scalars(
        select(Stocktake)
        .options(
            joinedload(Stocktake.items).joinedload(StocktakeItem.part),
            joinedload(Stocktake.items).joinedload(StocktakeItem.discrepancy),
            joinedload(Stocktake.initiator),
        )
        .where(Stocktake.id == stocktake_id)
    ).unique().first()
    if st is None:
        raise BusinessError("盘点单不存在")
    return st


def _require_in_progress(st: Stocktake) -> None:
    if st.status != enums.STOCKTAKE_IN_PROGRESS:
        raise BusinessError(f"盘点单已结束（{st.status}），不可再操作")


def _loc_equal(
    kind_a: Optional[str],
    id_a: Optional[int],
    kind_b: Optional[str],
    id_b: Optional[int],
) -> bool:
    return kind_a == kind_b and id_a == id_b


_LOC_MODELS = {
    enums.LOC_STORAGE: StorageLocation,
    enums.LOC_SERVER: Server,
    enums.LOC_EXTERNAL: ExternalOrg,
}


def _validate_actual_loc(
    db: Session,
    loc_kind: Optional[str],
    loc_id: Optional[int],
) -> None:
    """实际位置种类必须合法，且对应位置记录真实存在。"""
    if loc_kind is None:
        return
    model = _LOC_MODELS.get(loc_kind)
    if model is None:
        raise BusinessError(
            f"非法位置种类「{loc_kind}」，允许：{'/'.join(_LOC_MODELS)}"
        )
    if loc_id is None:
        raise BusinessError(f"位置种类为「{loc_kind}」时必须提供位置 ID")
    if db.get(model, loc_id) is None:
        raise BusinessError(f"位置不存在：{loc_kind} #{loc_id}")


def _clear_discrepancy(db: Session, item: StocktakeItem) -> None:
    if item.discrepancy is not None:
        db.delete(item.discrepancy)
        item.discrepancy = None
        db.flush()


def _upsert_discrepancy(
    db: Session,
    item: StocktakeItem,
    discrepancy_type: str,
) -> StocktakeDiscrepancy:
    status = (
        enums.DISC_STATUS_HOLD
        if discrepancy_type == enums.DISC_SHORTAGE
        else enums.DISC_STATUS_REVIEW
    )
    if item.discrepancy is not None:
        item.discrepancy.discrepancy_type = discrepancy_type
        item.discrepancy.status = status
        return item.discrepancy
    row = StocktakeDiscrepancy(
        stocktake_item_id=item.id,
        discrepancy_type=discrepancy_type,
        status=status,
    )
    db.add(row)
    db.flush()
    item.discrepancy = row
    return row


def create_stocktake(
    db: Session,
    *,
    initiator_id: int,
    scope_kind: str = enums.SCOPE_FULL,
    scope_value: Optional[dict] = None,
) -> Stocktake:
    if scope_kind not in enums.SCOPE_KINDS:
        raise BusinessError(f"非法 scope_kind: {scope_kind}")
    if scope_kind != enums.SCOPE_FULL:
        raise BusinessError("demo 仅支持发起「全盘」")
    _require_user(db, initiator_id)

    now = utcnow()
    st = Stocktake(
        scope_kind=scope_kind,
        scope_value=scope_value,
        initiator_id=initiator_id,
        initiated_at=now,
        snapshot_at=now,
        status=enums.STOCKTAKE_IN_PROGRESS,
    )
    db.add(st)
    db.flush()

    parts = list(db.scalars(select(Part).order_by(Part.id)).all())
    for part in parts:
        db.add(
            StocktakeItem(
                stocktake_id=st.id,
                part_id=part.id,
                expected_loc_kind=part.current_loc_kind,
                expected_loc_id=part.current_loc_id,
                result=enums.RESULT_PENDING,
            )
        )
    db.commit()
    return _get_stocktake(db, st.id)


def list_stocktakes(db: Session) -> list[Stocktake]:
    return list(
        db.scalars(select(Stocktake).order_by(Stocktake.id.desc())).all()
    )


def get_stocktake(db: Session, stocktake_id: int) -> Stocktake:
    return _get_stocktake(db, stocktake_id)


def summarize(st: Stocktake) -> dict:
    counts = {
        enums.RESULT_PENDING: 0,
        enums.RESULT_MATCH: 0,
        enums.RESULT_SHORTAGE: 0,
        enums.RESULT_SURPLUS: 0,
        enums.RESULT_MISPLACE: 0,
    }
    for item in st.items:
        counts[item.result] = counts.get(item.result, 0) + 1
    return counts


def check_item(
    db: Session,
    *,
    stocktake_id: int,
    operator_id: int,
    scanned_asset_no: Optional[str] = None,
    item_id: Optional[int] = None,
    actual_loc_kind: Optional[str] = None,
    actual_loc_id: Optional[int] = None,
    missing: bool = False,
) -> StocktakeItem:
    """现场清点三分支：账内报位置 / 账内找不到 / 查全表盘盈。"""
    _require_user(db, operator_id)
    st = _get_stocktake(db, stocktake_id)
    _require_in_progress(st)

    asset_no = (scanned_asset_no or "").strip() or None

    # ----- 分支 2：账内报找不到 -----
    if missing:
        item = _resolve_in_scope_item(db, st, asset_no=asset_no, item_id=item_id)
        if item.expected_loc_kind == enums.LOC_EXTERNAL:
            raise BusinessError("外单位件请走函证接口 /confirm-external，不可用现场清点报盘亏")
        item.result = enums.RESULT_SHORTAGE
        item.scanned_asset_no = asset_no or (
            item.part.fixed_asset_no if item.part else None
        )
        item.actual_loc_kind = None
        item.actual_loc_id = None
        item.checker_id = operator_id
        item.checked_at = utcnow()
        _upsert_discrepancy(db, item, enums.DISC_SHORTAGE)
        db.commit()
        return _reload_item(db, item.id)

    if not asset_no:
        raise BusinessError("scanned_asset_no 必填")

    _validate_actual_loc(db, actual_loc_kind, actual_loc_id)

    # ----- 分支 3：查全表无件 → 盘盈 -----
    part_in_system = db.scalars(
        select(Part).where(Part.fixed_asset_no == asset_no)
    ).first()
    if part_in_system is None:
        # 同一编号重复扫码：幂等更新已有盘盈行，不重复登记
        existing = next(
            (
                i
                for i in st.items
                if i.result == enums.RESULT_SURPLUS and i.scanned_asset_no == asset_no
            ),
            None,
        )
        if existing is not None:
            existing.actual_loc_kind = actual_loc_kind
            existing.actual_loc_id = actual_loc_id
            existing.checker_id = operator_id
            existing.checked_at = utcnow()
            db.commit()
            return _reload_item(db, existing.id)
        item = StocktakeItem(
            stocktake_id=st.id,
            part_id=None,
            expected_loc_kind=None,
            expected_loc_id=None,
            result=enums.RESULT_SURPLUS,
            actual_loc_kind=actual_loc_kind,
            actual_loc_id=actual_loc_id,
            scanned_asset_no=asset_no,
            checker_id=operator_id,
            checked_at=utcnow(),
        )
        db.add(item)
        db.flush()
        _upsert_discrepancy(db, item, enums.DISC_SURPLUS)
        db.commit()
        return _reload_item(db, item.id)

    # 系统有账：必须落在本单明细，否则范围外（非盘盈）
    item = next(
        (i for i in st.items if i.part_id == part_in_system.id and i.result != enums.RESULT_SURPLUS),
        None,
    )
    # 也匹配已有盘盈之外、含待复核/已盘的账内行
    if item is None:
        item = next((i for i in st.items if i.part_id == part_in_system.id), None)
    if item is None:
        raise BusinessError(
            f"固定资产编号 {asset_no} 在系统有账但不在本盘点单范围内，不能记为盘盈"
        )

    if item.expected_loc_kind == enums.LOC_EXTERNAL:
        raise BusinessError("外单位件请走函证接口 /confirm-external")

    # ----- 分支 1：账内报位置 -----
    if not actual_loc_kind:
        raise BusinessError("账内清点必须提供 actual_loc_kind，或使用 missing=true 报盘亏")

    item.scanned_asset_no = asset_no
    item.actual_loc_kind = actual_loc_kind
    item.actual_loc_id = actual_loc_id
    item.checker_id = operator_id
    item.checked_at = utcnow()

    if _loc_equal(
        actual_loc_kind, actual_loc_id, item.expected_loc_kind, item.expected_loc_id
    ):
        item.result = enums.RESULT_MATCH
        _clear_discrepancy(db, item)
    else:
        item.result = enums.RESULT_MISPLACE
        _upsert_discrepancy(db, item, enums.DISC_MISPLACE)

    db.commit()
    return _reload_item(db, item.id)


def _resolve_in_scope_item(
    db: Session,
    st: Stocktake,
    *,
    asset_no: Optional[str],
    item_id: Optional[int],
) -> StocktakeItem:
    if item_id is not None:
        item = next((i for i in st.items if i.id == item_id), None)
        if item is None:
            raise BusinessError("明细不存在或不属于本盘点单")
        if item.part_id is None:
            raise BusinessError("盘盈明细不能报账内盘亏")
        # 同时传入 asset_no 和 item_id 时校验一致性
        if asset_no and item.part is not None and item.part.fixed_asset_no != asset_no:
            raise BusinessError(
                f"资产编号 {asset_no} 与明细 #{item_id} 对应的 {item.part.fixed_asset_no} 不一致"
            )
        return item
    if not asset_no:
        raise BusinessError("missing=true 时须提供 scanned_asset_no 或 item_id")
    part = db.scalars(select(Part).where(Part.fixed_asset_no == asset_no)).first()
    if part is None:
        raise BusinessError("系统无此固定资产编号，不能用 missing 报盘亏；请走盘盈分支")
    item = next((i for i in st.items if i.part_id == part.id), None)
    if item is None:
        raise BusinessError("该配件不在本盘点单范围内")
    return item


def _reload_item(db: Session, item_id: int) -> StocktakeItem:
    item = db.scalars(
        select(StocktakeItem)
        .options(
            joinedload(StocktakeItem.part),
            joinedload(StocktakeItem.discrepancy),
        )
        .where(StocktakeItem.id == item_id)
    ).unique().first()
    if item is None:
        raise BusinessError("明细不存在")
    return item


def confirm_external(
    db: Session,
    *,
    stocktake_id: int,
    operator_id: int,
    item_id: int,
    present: bool,
    feedback_source: str,
) -> StocktakeItem:
    _require_user(db, operator_id)
    st = _get_stocktake(db, stocktake_id)
    _require_in_progress(st)

    source = (feedback_source or "").strip()
    if not source:
        raise BusinessError("函证必须填写 feedback_source")

    item = next((i for i in st.items if i.id == item_id), None)
    if item is None:
        raise BusinessError("明细不存在或不属于本盘点单")
    if item.expected_loc_kind != enums.LOC_EXTERNAL:
        raise BusinessError("仅外单位件可走函证")

    item.feedback_source = source
    item.checker_id = operator_id
    item.checked_at = utcnow()
    if item.part is not None:
        item.scanned_asset_no = item.part.fixed_asset_no

    if present:
        item.result = enums.RESULT_MATCH
        item.actual_loc_kind = item.expected_loc_kind
        item.actual_loc_id = item.expected_loc_id
        _clear_discrepancy(db, item)
    else:
        item.result = enums.RESULT_SHORTAGE
        item.actual_loc_kind = None
        item.actual_loc_id = None
        _upsert_discrepancy(db, item, enums.DISC_SHORTAGE)

    db.commit()
    return _reload_item(db, item.id)


def list_discrepancies(db: Session, stocktake_id: int) -> list[StocktakeDiscrepancy]:
    st = _get_stocktake(db, stocktake_id)
    rows = []
    for item in st.items:
        if item.discrepancy is not None:
            rows.append(item.discrepancy)
    return rows


def complete_stocktake(db: Session, *, stocktake_id: int, operator_id: int) -> Stocktake:
    _require_user(db, operator_id)
    st = _get_stocktake(db, stocktake_id)
    _require_in_progress(st)
    pending = [i for i in st.items if i.result == enums.RESULT_PENDING]
    if pending:
        raise BusinessError(
            f"尚有 {len(pending)} 条明细为「待复核」，不能结案"
        )
    st.status = enums.STOCKTAKE_COMPLETED
    db.commit()
    return _get_stocktake(db, st.id)


def assert_stocktake_read_only_red_line() -> None:
    """静态红线：盘点服务不得依赖写履历/改投影入口。"""
    import ast
    from pathlib import Path

    path = Path(__file__).resolve()
    tree = ast.parse(path.read_text(encoding="utf-8"))

    # 禁止从任意模块导入这些写入口名；用字符拼接避免自检误伤
    forbidden = {
        "insert" + "_movement",
        "apply_projection_from_" + "movement",
        "Movement" + "Log",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in forbidden:
                    raise RuntimeError(
                        f"盘点红线违反：不得 from-import {alias.name}"
                    )
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in forbidden:
                raise RuntimeError(f"盘点红线违反：调用 {func.id}")
            if isinstance(func, ast.Attribute) and func.attr in forbidden:
                raise RuntimeError(f"盘点红线违反：调用 .{func.attr}")
