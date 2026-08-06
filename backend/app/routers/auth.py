from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enums
from ..database import get_db
from ..deps import (
    get_current_user,
    hash_password,
    make_token,
    needs_password_upgrade,
    require_role,
    verify_password,
)
from ..models import User

router = APIRouter(tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    token: str
    user_id: int
    username: str
    name: str
    role: str


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str


class RegisterIn(BaseModel):
    username: str
    password: str
    name: str
    applied_role: str
    apply_reason: str


class RegisterOut(BaseModel):
    id: int
    username: str
    name: str
    applied_role: str
    status: str


class RegistrationOut(BaseModel):
    id: int
    username: Optional[str] = None
    name: str
    role: str
    applied_role: Optional[str] = None
    apply_reason: Optional[str] = None
    status: str
    reject_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class RejectIn(BaseModel):
    reason: str


def _user_out(user: User, token: str) -> dict:
    return {
        "token": token,
        "user_id": user.id,
        "username": user.username,
        "name": user.name,
        "role": user.role,
    }


@router.post("/auth/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    key = body.username.strip()
    user = db.scalars(select(User).where(User.username == key)).first()
    # 兼容用显示名登录（如「张运维」）
    if user is None:
        user = db.scalars(select(User).where(User.name == key)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not verify_password(user, body.password):
        raise HTTPException(status_code=401, detail="密码错误")
    # 账号状态拦截（自助注册审批流）
    if user.status == enums.USER_STATUS_PENDING:
        raise HTTPException(status_code=403, detail="账号正在等待领导审批，暂不能登录")
    if user.status == enums.USER_STATUS_REJECTED:
        reason = f"：{user.reject_reason}" if user.reject_reason else ""
        raise HTTPException(status_code=403, detail=f"注册申请已被驳回{reason}，可修改后重新注册")
    if user.status == enums.USER_STATUS_DISABLED:
        raise HTTPException(status_code=403, detail="账号已停用，请联系管理员")
    # 旧无盐 sha256 校验通过后顺势升级为 PBKDF2
    if needs_password_upgrade(user):
        user.password_hash = hash_password(body.password)
        db.commit()
    return _user_out(user, make_token(user))


@router.get("/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "name": current_user.name,
        "role": current_user.role,
    }


@router.post("/auth/change-password")
def change_password(
    body: ChangePasswordIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(current_user, body.old_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


# ---------- 自助注册 + 领导审批 ----------

@router.post("/auth/register", response_model=RegisterOut)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """公开注册入口：创建「待审核」账号，由领导在审批中心通过后生效。"""
    username = body.username.strip()
    name = body.name.strip()
    reason = body.apply_reason.strip()
    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少 3 个字符")
    if not username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="用户名仅允许字母、数字、下划线、短横线")
    if not name:
        raise HTTPException(status_code=400, detail="姓名必填")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    if body.applied_role not in enums.SELF_REGISTER_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"申请角色仅允许：{' / '.join(enums.SELF_REGISTER_ROLES)}（领导角色由管理员授予）",
        )
    if not reason:
        raise HTTPException(status_code=400, detail="请填写申请理由，便于审批人判断")
    clash = db.scalars(select(User).where(User.username == username)).first()
    if clash is not None:
        raise HTTPException(status_code=400, detail=f"用户名已被占用：{username}")

    user = User(
        username=username,
        name=name,
        role_label=body.applied_role,
        role=body.applied_role,  # 生效与否由 status 门控
        password_hash=hash_password(body.password),
        status=enums.USER_STATUS_PENDING,
        applied_role=body.applied_role,
        apply_reason=reason,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/auth/registrations", response_model=list[RegistrationOut])
def list_registrations(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """注册申请列表（默认看待审核），仅领导可见。"""
    require_role(current_user, (enums.ROLE_LEADER,))
    stmt = select(User).where(User.applied_role.is_not(None)).order_by(User.id.desc())
    if status:
        stmt = stmt.where(User.status == status)
    else:
        stmt = stmt.where(User.status == enums.USER_STATUS_PENDING)
    return list(db.scalars(stmt).all())


@router.post("/auth/registrations/{user_id}/approve", response_model=RegistrationOut)
def approve_registration(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    user = db.get(User, user_id)
    if user is None or user.applied_role is None:
        raise HTTPException(status_code=404, detail="注册申请不存在")
    if user.status != enums.USER_STATUS_PENDING:
        raise HTTPException(status_code=400, detail=f"该申请当前状态为「{user.status}」，不能审批")
    user.status = enums.USER_STATUS_ACTIVE
    user.role = user.applied_role
    user.role_label = user.applied_role
    user.reviewed_by_id = current_user.id
    user.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


@router.post("/auth/registrations/{user_id}/reject", response_model=RegistrationOut)
def reject_registration(
    user_id: int,
    body: RejectIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    user = db.get(User, user_id)
    if user is None or user.applied_role is None:
        raise HTTPException(status_code=404, detail="注册申请不存在")
    if user.status != enums.USER_STATUS_PENDING:
        raise HTTPException(status_code=400, detail=f"该申请当前状态为「{user.status}」，不能审批")
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="驳回必须填写理由")
    user.status = enums.USER_STATUS_REJECTED
    user.reject_reason = body.reason.strip()
    user.reviewed_by_id = current_user.id
    user.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


# ---------- 用户管理（领导）：新增用户 / 调整角色与状态 ----------

class UserAdminOut(BaseModel):
    id: int
    username: Optional[str] = None
    name: str
    role: str
    status: str
    applied_role: Optional[str] = None
    apply_reason: Optional[str] = None
    reject_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class UserCreateIn(BaseModel):
    username: str
    password: str
    name: str
    role: str


class UserPatchIn(BaseModel):
    role: Optional[str] = None
    status: Optional[str] = None


def _count_active_leaders(db: Session, exclude_id: Optional[int] = None) -> int:
    stmt = select(User).where(
        User.role == enums.ROLE_LEADER,
        User.status == enums.USER_STATUS_ACTIVE,
    )
    n = 0
    for u in db.scalars(stmt).all():
        if exclude_id is not None and u.id == exclude_id:
            continue
        n += 1
    return n


@router.get("/auth/users", response_model=list[UserAdminOut])
def admin_list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, (enums.ROLE_LEADER,))
    return list(db.scalars(select(User).order_by(User.id)).all())


@router.post("/auth/users", response_model=UserAdminOut)
def admin_create_user(
    body: UserCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """领导直接创建账号（含领导角色），立即生效，无需审批。"""
    require_role(current_user, (enums.ROLE_LEADER,))
    username = body.username.strip()
    name = body.name.strip()
    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少 3 个字符")
    if not username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="用户名仅允许字母、数字、下划线、短横线")
    if not name:
        raise HTTPException(status_code=400, detail="姓名必填")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    if body.role not in enums.ROLES:
        raise HTTPException(status_code=400, detail=f"非法角色「{body.role}」，允许：{' / '.join(enums.ROLES)}")
    clash = db.scalars(select(User).where(User.username == username)).first()
    if clash is not None:
        raise HTTPException(status_code=400, detail=f"用户名已被占用：{username}")
    user = User(
        username=username,
        name=name,
        role_label=body.role,
        role=body.role,
        password_hash=hash_password(body.password),
        status=enums.USER_STATUS_ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/auth/users/{user_id}", response_model=UserAdminOut)
def admin_patch_user(
    user_id: int,
    body: UserPatchIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """调整用户角色 / 停用启用。护栏：不能改自己；不能动最后一个在用的领导。"""
    require_role(current_user, (enums.ROLE_LEADER,))
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能修改自己的角色或状态，请由其他领导操作")

    new_role = body.role if body.role is not None else user.role
    new_status = body.status if body.status is not None else user.status
    if new_role not in enums.ROLES:
        raise HTTPException(status_code=400, detail=f"非法角色「{new_role}」")
    if new_status not in (enums.USER_STATUS_ACTIVE, enums.USER_STATUS_DISABLED):
        raise HTTPException(status_code=400, detail="状态仅允许：正常 / 停用")
    # 最后一个领导保护
    if user.role == enums.ROLE_LEADER and (
        new_role != enums.ROLE_LEADER or new_status != enums.USER_STATUS_ACTIVE
    ):
        if _count_active_leaders(db, exclude_id=user.id) == 0:
            raise HTTPException(status_code=400, detail="系统至少保留一个在用的「领导」账号")

    user.role = new_role
    user.role_label = new_role
    user.status = new_status
    db.commit()
    db.refresh(user)
    return user
