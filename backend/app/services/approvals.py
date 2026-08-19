from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .. import enums
from ..models import Approval, ApprovalStep, ExternalOrg, Part, User
from .movement import (
    BusinessError,
    apply_projection_from_movement,
    insert_movement,
    require_status,
)

# 各审批动作的发起/落履历规则（单一真相源）
# allowed_status: 发起与末级落履历前都重校验的起始状态白名单
# event_type / status_to / loc_to_kind: 末级通过后落履历的写法
_ACTION_RULES = {
    enums.ACTION_LOAN: {
        "allowed_status": {enums.STATUS_IN_STOCK},
        "event_type": enums.EVENT_LOAN,
        "status_to": enums.STATUS_LOANED,
        "loc_to_kind": enums.LOC_EXTERNAL,
    },
    enums.ACTION_TRANSFER: {
        "allowed_status": {enums.STATUS_IN_STOCK},
        "event_type": enums.EVENT_TRANSFER,
        "status_to": enums.STATUS_TRANSFERRED,
        "loc_to_kind": enums.LOC_EXTERNAL,
    },
    enums.ACTION_SCRAP: {
        "allowed_status": {enums.STATUS_IN_STOCK, enums.STATUS_DAMAGED},
        "event_type": enums.EVENT_SCRAP,
        "status_to": enums.STATUS_SCRAPPED,
        "loc_to_kind": enums.LOC_NONE,
    },
}

def _get_inflight_approval(db: Session, part_id: int) -> Optional[Approval]:
    """同一配件任意类型的「审批中」单（不限 action_type）。"""
    return db.scalars(
        select(Approval).where(
            Approval.part_id == part_id,
            Approval.overall_status == enums.APPROVAL_PENDING,
        )
    ).first()

def assert_no_inflight_approval(db: Session, part_id: int) -> None:
    """装机/拆下/报损/归还等变更前：禁止配件上存在审批中单据。"""
    inflight = _get_inflight_approval(db, part_id)
    if inflight is not None:
        raise BusinessError(
            f"配件存在审批中单据（#{inflight.id}「{inflight.action_type}」），"
            f"请先完成或撤回后再操作"
        )

def _validate_people(
    db: Session, *, applicant_id: int, approver_ids: list[int]
) -> None:
    if len(approver_ids) != 3:
        raise BusinessError("必须指定恰好三级审批人")
    if len(set(approver_ids)) != 3:
        raise BusinessError("三级审批人必须互不相同")
    if applicant_id in approver_ids:
        raise BusinessError("审批回避：申请人不得出现在任何一级审批人中")

    all_uids = [applicant_id, *approver_ids]
    users = {
        u.id: u
        for u in db.scalars(select(User).where(User.id.in_(all_uids))).all()
    }
    missing = [uid for uid in all_uids if uid not in users]
    if missing:
        raise BusinessError(f"用户不存在: {missing}")

    inactive = [
        f"{users[uid].name}（{getattr(users[uid], 'status', None) or '未知'}）"
        for uid in all_uids
        if getattr(users[uid], "status", enums.USER_STATUS_ACTIVE)
        != enums.USER_STATUS_ACTIVE
    ]
    if inactive:
        raise BusinessError(
            "申请人与审批人须为「正常」状态账号，下列用户不符合："
            + "、".join(inactive)
        )

    # 轻量权限：审批人须具备允许审批的角色
    approval_roles_display = " / ".join(enums.APPROVER_ROLES)
    bad = [
        f"{users[uid].name}（{users[uid].role or '无角色'}）"
        for uid in approver_ids
        if (users[uid].role or "") not in enums.APPROVER_ROLES
    ]
    if bad:
        raise BusinessError(
            f"审批人须为「{approval_roles_display}」角色，下列用户不符合："
            + "、".join(bad)
        )

def _require_dest_org(db: Session, dest_org_id: Optional[int]) -> None:
    if dest_org_id is None:
        raise BusinessError("必须指定外单位")
    if db.get(ExternalOrg, dest_org_id) is None:
        raise BusinessError("外单位不存在")

def _create_approval(
    db: Session,
    *,
    action_type: str,
    part_id: int,
    applicant_id: int,
    approver_ids: list[int],
    expected_return_date: Optional[date] = None,
    dest_org_id: Optional[int] = None,
    reason_code: Optional[str] = None,
    attachment_ref: Optional[str] = None,
    remark: Optional[str] = None,
    auto_approve: bool = False,
) -> Approval:
    rules = _ACTION_RULES[action_type]

    if not auto_approve:
        _validate_people(db, applicant_id=applicant_id, approver_ids=approver_ids)
    else:
        applicant = db.get(User, applicant_id)
        if applicant is None:
            raise BusinessError("申请人不存在")
        if applicant.status != enums.USER_STATUS_ACTIVE:
            raise BusinessError("超级管理员账号状态异常，不能执行免审批操作")

    part = db.scalars(
        select(Part).where(Part.id == part_id).with_for_update()
    ).first()
    if part is None:
        raise BusinessError("配件不存在")
    require_status(part, rules["allowed_status"], f"发起{action_type}")

    if _get_inflight_approval(db, part_id) is not None:
        raise BusinessError("该配件已有「审批中」的申请单，禁止重复发起")

    approval = Approval(
        part_id=part_id,
        action_type=action_type,
        applicant_id=applicant_id,
        applied_at=datetime.now(timezone.utc),
        overall_status=(
            enums.APPROVAL_APPROVED if auto_approve else enums.APPROVAL_PENDING
        ),
        current_level=0 if auto_approve else 1,
        expected_return_date=expected_return_date,
        dest_org_id=dest_org_id,
        reason_code=reason_code,
        attachment_ref=attachment_ref,
        remark=remark,
    )
    db.add(approval)
    db.flush()

    if auto_approve:
        if rules["loc_to_kind"] == enums.LOC_EXTERNAL:
            loc_to_kind = enums.LOC_EXTERNAL
            loc_to_id = approval.dest_org_id
        else:
            loc_to_kind = enums.LOC_NONE
            loc_to_id = None
        movement = insert_movement(
            db,
            part_id=part.id,
            event_type=rules["event_type"],
            status_from=part.current_status,
            status_to=rules["status_to"],
            operator_id=applicant_id,
            loc_from_kind=part.current_loc_kind,
            loc_from_id=part.current_loc_id,
            loc_to_kind=loc_to_kind,
            loc_to_id=loc_to_id,
            approval_id=approval.id,
            expected_return_date=approval.expected_return_date,
            reason_code=approval.reason_code,
            remark=approval.remark,
        )
        apply_projection_from_movement(part, movement)
        db.commit()
        return get_approval(db, approval.id)

    for level, approver_id in enumerate(approver_ids, start=1):
        # 仅第 1 级为「待审」；其余级等待激活（状态仍用待审，靠 current_level 门禁）
        db.add(
            ApprovalStep(
                approval_id=approval.id,
                level=level,
                approver_id=approver_id,
                step_status=enums.STEP_PENDING,
            )
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # 数据库部分唯一索引是并发场景下的最终防线。
        if "uq_approval_pending_part" in str(exc) or "approval.part_id" in str(exc):
            raise BusinessError("该配件已有「审批中」的申请单，禁止重复发起") from exc
        raise
    db.refresh(approval)
    return get_approval(db, approval.id)

def create_loan_approval(
    db: Session,
    *,
    part_id: int,
    applicant_id: int,
    dest_org_id: int,
    expected_return_date: date,
    approver_ids: list[int],
    remark: Optional[str] = None,
    auto_approve: bool = False,
) -> Approval:
    if expected_return_date is None:
        raise BusinessError("借出必须填写预期归还日")
    if expected_return_date < date.today():
        raise BusinessError("预期归还日不得早于申请当日")
    _require_dest_org(db, dest_org_id)
    return _create_approval(
        db,
        action_type=enums.ACTION_LOAN,
        part_id=part_id,
        applicant_id=applicant_id,
        approver_ids=approver_ids,
        expected_return_date=expected_return_date,
        dest_org_id=dest_org_id,
        remark=remark,
        auto_approve=auto_approve,
    )

def create_transfer_approval(
    db: Session,
    *,
    part_id: int,
    applicant_id: int,
    dest_org_id: int,
    approver_ids: list[int],
    reason_code: Optional[str] = None,
    remark: Optional[str] = None,
    auto_approve: bool = False,
) -> Approval:
    _require_dest_org(db, dest_org_id)
    return _create_approval(
        db,
        action_type=enums.ACTION_TRANSFER,
        part_id=part_id,
        applicant_id=applicant_id,
        approver_ids=approver_ids,
        dest_org_id=dest_org_id,
        reason_code=(reason_code or "").strip() or None,
        remark=remark,
        auto_approve=auto_approve,
    )

def create_scrap_approval(
    db: Session,
    *,
    part_id: int,
    applicant_id: int,
    approver_ids: list[int],
    reason_code: str,
    attachment_ref: Optional[str] = None,
    remark: Optional[str] = None,
    auto_approve: bool = False,
) -> Approval:
    if reason_code not in enums.REASON_CODES_SCRAP:
        raise BusinessError(
            f"非法报废缘由「{reason_code}」，允许：{'/'.join(enums.REASON_CODES_SCRAP)}"
        )
    part = db.get(Part, part_id)
    if part is None:
        raise BusinessError("配件不存在")
    # 高值件（算力卡类）报废必须留影像证据（设计 6.3 防掉包，按配件类型判断）
    if (
        part.model
        and part.model.category in enums.SCRAP_ATTACHMENT_CATEGORIES
        and not (attachment_ref or "").strip()
    ):
        raise BusinessError(
            f"该配件为「{part.model.category}」高值件，报废必须提供影像证据（attachment_ref）"
        )
    return _create_approval(
        db,
        action_type=enums.ACTION_SCRAP,
        part_id=part_id,
        applicant_id=applicant_id,
        approver_ids=approver_ids,
        reason_code=reason_code,
        attachment_ref=(attachment_ref or "").strip() or None,
        remark=remark,
        auto_approve=auto_approve,
    )

def get_approval(db: Session, approval_id: int) -> Approval:
    approval = db.scalars(
        select(Approval)
        .options(
            joinedload(Approval.steps).joinedload(ApprovalStep.approver),
            joinedload(Approval.applicant),
            joinedload(Approval.dest_org),
            joinedload(Approval.part),
        )
        .where(Approval.id == approval_id)
    ).unique().first()
    if approval is None:
        raise BusinessError("审批单不存在")
    return approval

def list_approvals(db: Session) -> list[Approval]:
    return list(
        db.scalars(
            select(Approval)
            .options(
                joinedload(Approval.steps).joinedload(ApprovalStep.approver),
                joinedload(Approval.applicant),
                joinedload(Approval.dest_org),
                joinedload(Approval.part),
            )
            .order_by(Approval.id.desc())
        )
        .unique()
        .all()
    )

def withdraw_approval(
    db: Session, *, approval_id: int, operator_id: int
) -> Approval:
    """撤回：仅申请人本人、仅审批中；不写任何履历，已通过环节留痕。"""
    approval = get_approval(db, approval_id)
    if approval.overall_status != enums.APPROVAL_PENDING:
        raise BusinessError(f"审批单已结束（{approval.overall_status}），不可撤回")
    if operator_id != approval.applicant_id:
        raise BusinessError("仅申请人本人可撤回")
    approval.overall_status = enums.APPROVAL_WITHDRAWN
    db.commit()
    return get_approval(db, approval_id)

def _void_approval(db: Session, approval: Approval, reason: str) -> None:
    """落履历前状态校验失败：审批作废（驳回 + 系统原因）。"""
    approval.overall_status = enums.APPROVAL_REJECTED
    approval.remark = (approval.remark or "") + f"【系统作废】{reason}"
    # 末级已点「通过」但未落履历：回滚该步，避免 UI 显示 L3 通过而整体驳回
    for step in approval.steps:
        if (
            step.level == approval.current_level
            and step.step_status == enums.STEP_APPROVED
        ):
            step.step_status = enums.STEP_REJECTED
            note = f"【系统作废】{reason}"
            step.opinion = (
                f"{step.opinion}；{note}" if step.opinion else note
            )
            break
    db.commit()

def decide_approval(
    db: Session,
    *,
    approval_id: int,
    operator_id: int,
    level: int,
    approve: bool,
    opinion: Optional[str] = None,
) -> Approval:
    approval = get_approval(db, approval_id)
    if approval.overall_status != enums.APPROVAL_PENDING:
        raise BusinessError(f"审批单已结束（{approval.overall_status}），不可再审")
    if level != approval.current_level:
        raise BusinessError(
            f"当前应审第 {approval.current_level} 级，不能审第 {level} 级"
        )

    step = next((s for s in approval.steps if s.level == level), None)
    if step is None:
        raise BusinessError("审批环节不存在")
    if operator_id != step.approver_id:
        raise BusinessError("非本级指定审批人，无权审批")
    if step.step_status != enums.STEP_PENDING:
        raise BusinessError("该级已审，不可重复审批")

    step.step_status = enums.STEP_APPROVED if approve else enums.STEP_REJECTED
    step.opinion = opinion
    step.decided_at = datetime.now(timezone.utc)

    if not approve:
        approval.overall_status = enums.APPROVAL_REJECTED
        db.commit()
        return get_approval(db, approval_id)

    # 通过
    if level < 3:
        approval.current_level = level + 1
        db.commit()
        return get_approval(db, approval_id)

    # 末级通过：落履历前按动作规则重校验起始状态，并加行锁防竞态
    rules = _ACTION_RULES[approval.action_type]
    allowed = rules["allowed_status"]

    part = db.scalars(
        select(Part).where(Part.id == approval.part_id).with_for_update()
    ).first()
    if part is None:
        raise BusinessError("配件不存在")
    if part.current_status not in allowed:
        _void_approval(
            db,
            approval,
            f"落履历前配件状态为「{part.current_status}」，"
            f"不满足「{approval.action_type}」要求（允许：{'/'.join(sorted(allowed))}）",
        )
        raise BusinessError(
            f"审批完成时配件状态已变化（当前「{part.current_status}」），审批已作废，未写入履历"
        )

    # 报废/调拨（终态）离场无外单位；借出/调拨去外单位
    if rules["loc_to_kind"] == enums.LOC_EXTERNAL:
        loc_to_kind = enums.LOC_EXTERNAL
        loc_to_id = approval.dest_org_id
    else:
        loc_to_kind = enums.LOC_NONE
        loc_to_id = None

    movement = insert_movement(
        db,
        part_id=part.id,
        event_type=rules["event_type"],
        status_from=part.current_status,
        status_to=rules["status_to"],
        operator_id=operator_id,  # 实际审批人，非申请人
        loc_from_kind=part.current_loc_kind,
        loc_from_id=part.current_loc_id,
        loc_to_kind=loc_to_kind,
        loc_to_id=loc_to_id,
        approval_id=approval.id,
        expected_return_date=approval.expected_return_date,
        reason_code=approval.reason_code,
        remark=approval.remark,
    )
    apply_projection_from_movement(part, movement)
    approval.overall_status = enums.APPROVAL_APPROVED
    db.commit()
    return get_approval(db, approval_id)
