from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from .models import User


def get_operator_id(
    x_operator_id: int = Header(..., alias="X-Operator-Id"),
) -> int:
    return x_operator_id


def require_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=400, detail=f"操作人不存在: {user_id}")
    return user
