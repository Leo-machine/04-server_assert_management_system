from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ExternalOrg, Server, StorageLocation, User
from ..schemas import (
    ExternalOrgOut,
    ServerOut,
    ServerRunStatusIn,
    StorageLocationOut,
    UserOut,
)
from ..services.movement import BusinessError
from ..services import parts as parts_service

router = APIRouter(tags=["catalog"])


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return list(db.scalars(select(User).order_by(User.id)).all())


@router.get("/servers", response_model=list[ServerOut])
def list_servers(db: Session = Depends(get_db)):
    return list(db.scalars(select(Server).order_by(Server.id)).all())


@router.patch("/servers/{server_id}/run-status", response_model=ServerOut)
def patch_run_status(
    server_id: int,
    body: ServerRunStatusIn,
    db: Session = Depends(get_db),
):
    try:
        return parts_service.set_server_run_status(db, server_id, body.run_status)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.get("/storage-locations", response_model=list[StorageLocationOut])
def list_locations(db: Session = Depends(get_db)):
    return list(db.scalars(select(StorageLocation).order_by(StorageLocation.id)).all())


@router.get("/external-orgs", response_model=list[ExternalOrgOut])
def list_orgs(db: Session = Depends(get_db)):
    return list(db.scalars(select(ExternalOrg).order_by(ExternalOrg.id)).all())
