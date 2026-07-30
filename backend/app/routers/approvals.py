from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_operator_id, require_user
from ..schemas import ApprovalOut, DecideIn, LoanApprovalIn
from ..services.movement import BusinessError
from ..services import approvals as approvals_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalOut])
def list_approvals(db: Session = Depends(get_db)):
    return approvals_service.list_approvals(db)


@router.get("/{approval_id}", response_model=ApprovalOut)
def get_approval(approval_id: int, db: Session = Depends(get_db)):
    try:
        return approvals_service.get_approval(db, approval_id)
    except BusinessError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@router.post("/loan", response_model=ApprovalOut)
def create_loan(
    body: LoanApprovalIn,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    require_user(db, operator_id)
    try:
        return approvals_service.create_loan_approval(
            db,
            part_id=body.part_id,
            applicant_id=operator_id,
            dest_org_id=body.dest_org_id,
            expected_return_date=body.expected_return_date,
            approver_ids=body.approver_ids,
            remark=body.remark,
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.post("/{approval_id}/decide", response_model=ApprovalOut)
def decide(
    approval_id: int,
    body: DecideIn,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    require_user(db, operator_id)
    try:
        return approvals_service.decide_approval(
            db,
            approval_id=approval_id,
            operator_id=operator_id,
            level=body.level,
            approve=body.approve,
            opinion=body.opinion,
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
