from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_operator_id, require_user
from ..schemas import SupplierIn, SupplierOut, SupplierUpdateIn
from ..services.movement import BusinessError
from ..services import suppliers as suppliers_service

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=list[SupplierOut])
def list_suppliers(db: Session = Depends(get_db)):
    return suppliers_service.list_suppliers(db)


@router.post("", response_model=SupplierOut)
def create_supplier(
    body: SupplierIn,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    require_user(db, operator_id)
    try:
        return suppliers_service.create_supplier(db, **body.model_dump())
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.put("/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: int,
    body: SupplierUpdateIn,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    require_user(db, operator_id)
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
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.delete("/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    operator_id: int = Depends(get_operator_id),
):
    require_user(db, operator_id)
    try:
        suppliers_service.delete_supplier(db, supplier_id)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    return {"ok": True}
