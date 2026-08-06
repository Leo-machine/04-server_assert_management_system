from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enums
from ..database import get_db
from ..deps import get_current_user, require_role
from ..models import ExternalOrg, Server, ServerMovementLog, User
from ..schemas import (
    ExternalOrgOut,
    ServerDetailOut,
    ServerIn,
    ServerMovementOut,
    ServerOut,
    ServerRunStatusIn,
    ServerUpdateIn,
    UserOut,
)
from ..services.movement import BusinessError
from ..services import parts as parts_service
from ..services import servers as servers_service

router = APIRouter(tags=["catalog"])


class BatchImportIn(BaseModel):
    content: str  # CSV 文本（UTF-8）


def _csv_response(text: str, filename: str) -> Response:
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 审批人选人等场景：仅返回正常账号（无密码字段）
    return list(
        db.scalars(
            select(User)
            .where(User.status == enums.USER_STATUS_ACTIVE)
            .order_by(User.id)
        ).all()
    )


@router.get("/servers", response_model=list[ServerOut])
def list_servers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list(db.scalars(select(Server).order_by(Server.id)).all())


@router.get("/servers/export.csv")
def export_servers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.INVENTORY_ROLES)
    return _csv_response(servers_service.export_servers_csv(db), "servers_export.csv")


@router.get("/servers/import-template.csv")
def servers_import_template(current_user: User = Depends(get_current_user)):
    return _csv_response(
        servers_service.import_template_csv(), "servers_import_template.csv"
    )


@router.post("/servers/batch-import")
def batch_import_servers(
    body: BatchImportIn,
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """两段式批量导入：dry_run=true 校验预览；dry_run=false 整批通过才写入。"""
    require_role(current_user, (enums.ROLE_LEADER,))
    try:
        return servers_service.batch_import_servers(db, body.content, dry_run=dry_run)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.get("/servers/{server_id}", response_model=ServerDetailOut)
def get_server(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """服务器详情：档案字段 + 当前安装配件清单。"""
    try:
        detail = servers_service.get_server_detail(db, server_id)
    except BusinessError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    server = detail["server"]
    base = ServerOut.model_validate(server).model_dump()
    return ServerDetailOut(
        **base,
        installed_parts=detail["installed_parts"],
        installed_count=detail["installed_count"],
        installed_by_category=detail["installed_by_category"],
    )


@router.post("/servers", response_model=ServerOut)
def create_server(
    body: ServerIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    try:
        return servers_service.create_server(db, **body.model_dump())
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.put("/servers/{server_id}", response_model=ServerOut)
def update_server(
    server_id: int,
    body: ServerUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    try:
        return servers_service.update_server(
            db, server_id, **body.model_dump(exclude_unset=True)
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.delete("/servers/{server_id}")
def delete_server(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    try:
        servers_service.delete_server(db, server_id)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    return {"ok": True}


@router.patch("/servers/{server_id}/run-status", response_model=ServerOut)
def patch_run_status(
    server_id: int,
    body: ServerRunStatusIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, enums.INSTALL_UNINSTALL_ROLES)
    try:
        return parts_service.set_server_run_status(
            db, server_id, body.run_status,
            work_order_no=body.work_order_no, operator_id=current_user.id,
        )
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.get("/servers/{server_id}/movements", response_model=list[ServerMovementOut])
def server_movements(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list(db.scalars(
        select(ServerMovementLog)
        .where(ServerMovementLog.server_id == server_id)
        .order_by(ServerMovementLog.occurred_at.desc(), ServerMovementLog.id.desc())
    ).all())


@router.get("/external-orgs", response_model=list[ExternalOrgOut])
def list_orgs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list(db.scalars(select(ExternalOrg).order_by(ExternalOrg.id)).all())
