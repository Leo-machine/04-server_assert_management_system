from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import enums
from ..deps import get_current_user, require_role
from ..models import User
from ..schemas import SupplierIn, SupplierOut, SupplierUpdateIn
from ..services.movement import BusinessError
from ..services import suppliers as suppliers_service

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=list[SupplierOut])
def list_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return suppliers_service.list_suppliers(db)


@router.post("", response_model=SupplierOut)
def create_supplier(
    body: SupplierIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    try:
        return suppliers_service.create_supplier(db, **body.model_dump())
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.put("/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: int,
    body: SupplierUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    payload = body.model_dump(exclude_unset=True)
    try:
        return suppliers_service.update_supplier(
            db,
            supplier_id,
            name=payload.get("name"),
            contact=payload.get("contact"),
            contact_info=payload.get("contact_info"),
            remark=payload.get("remark"),
            set_contact="contact" in payload,
            set_contact_info="contact_info" in payload,
            set_remark="remark" in payload,
            asset_category_ids=payload.get("asset_category_ids"),
            set_asset_category_ids="asset_category_ids" in payload,
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.delete("/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    try:
        suppliers_service.delete_supplier(db, supplier_id)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    return {"ok": True}
