from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import (
    get_current_user,
    hash_password,
    make_token,
    needs_password_upgrade,
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
