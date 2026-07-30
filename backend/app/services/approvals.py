from datetime import date, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .. import enums
from ..models import Approval, ApprovalStep, ExternalOrg, Part, User
from .movement import (
    BusinessError,
    apply_projection_from_movement,
    insert_movement,
    require_status,
)


def _get_inflight_loan(db: Session, part_id: int) -> Optional[Approval]:
    return db.scalars(
        select(Approval).where(
            Approval.part_id == part_id,
            Approval.action_type == enums.ACTION_LOAN,
            Approval.overall_status == enums.APPROVAL_PENDING,
        )
    ).first()


def create_loan_approval(
    db: Session,
    *,
    part_id: int,
    applicant_id: int,
    dest_org_id: int,
    expected_return_date: date,
    approver_ids: list[int],
    remark: Optional[str] = None,
) -> Approval:
    if expected_return_date is None:
        raise BusinessError("借出必须填写预期归还日")
    if len(approver_ids) != 3:
        raise BusinessError("必须指定恰好三级审批人")
    if len(set(approver_ids)) != 3:
        raise BusinessError("三级审批人必须互不相同")
    if applicant_id in approver_ids:
        raise BusinessError("审批回避：申请人不得出现在任何一级审批人中")

    part = db.get(Part, part_id)
    if part is None:
        raise BusinessError("配件不存在")
    require_status(part, {enums.STATUS_IN_STOCK}, "发起借出")

    if _get_inflight_loan(db, part_id) is not None:
        raise BusinessError("该配件已有「审批中」的借出单，禁止重复发起")

    org = db.get(ExternalOrg, dest_org_id)
    if org is None:
        raise BusinessError("外单位不存在")
    for uid in [applicant_id, *approver_ids]:
        if db.get(User, uid) is None:
            raise BusinessError(f"用户不存在: {uid}")

    approval = Approval(
        part_id=part_id,
        action_type=enums.ACTION_LOAN,
        applicant_id=applicant_id,
        applied_at=datetime.utcnow(),
        overall_status=enums.APPROVAL_PENDING,
        current_level=1,
        expected_return_date=expected_return_date,
        dest_org_id=dest_org_id,
        remark=remark,
    )
    db.add(approval)
    db.flush()

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
    db.commit()
    db.refresh(approval)
    return get_approval(db, approval.id)


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

    step.step_status = enums.STEP_APPROVED if approve else enums.STEP_REJECTED
    step.opinion = opinion
    step.decided_at = datetime.utcnow()

    if not approve:
        approval.overall_status = enums.APPROVAL_REJECTED
        db.commit()
        return get_approval(db, approval_id)

    # 通过
    if level < 3:
        approval.current_level = level + 1
        db.commit()
        return get_approval(db, approval_id)

    # 末级通过：落履历前重校验仍在库
    part = db.get(Part, approval.part_id)
    if part is None:
        raise BusinessError("配件不存在")
    if part.current_status != enums.STATUS_IN_STOCK:
        approval.overall_status = enums.APPROVAL_REJECTED
        # 用意见记录作废原因，便于排查
        step.opinion = (opinion or "") + (
            f"【系统作废】落履历前配件状态为「{part.current_status}」，非在库，审批作废"
        )
        db.commit()
        raise BusinessError(
            f"审批完成时配件已不在库（当前「{part.current_status}」），审批已作废，未写入借出履历"
        )

    from_kind = part.current_loc_kind
    from_id = part.current_loc_id

    movement = insert_movement(
        db,
        part_id=part.id,
        event_type=enums.EVENT_LOAN,
        status_from=part.current_status,
        status_to=enums.STATUS_LOANED,
        operator_id=approval.applicant_id,
        loc_from_kind=from_kind,
        loc_from_id=from_id,
        loc_to_kind=enums.LOC_EXTERNAL,
        loc_to_id=approval.dest_org_id,
        approval_id=approval.id,
        expected_return_date=approval.expected_return_date,
        remark=approval.remark,
    )
    apply_projection_from_movement(part, movement)
    approval.overall_status = enums.APPROVAL_APPROVED
    db.commit()
    return get_approval(db, approval_id)
