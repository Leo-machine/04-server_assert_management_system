"""认证与授权。

令牌：wb1-<base64url(user_id:expiry_ts):hmac_sha256签名>
- 签名用服务端密钥（env APP_SECRET，缺省生成并持久化到 data/.secret）
- 角色/权限一律从 DB 读，不信任令牌内容；改角色即时生效
- 默认 12 小时过期
密码：PBKDF2-HMAC-SHA256（兼容旧无盐 sha256，验证成功后自动升级）
"""

import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .database import DB_PATH, get_db
from .models import User

TOKEN_PREFIX = "wb1-"
TOKEN_TTL_SECONDS = 12 * 3600
_PBKDF2_ITERATIONS = 100_000

# ---------- 密钥 ----------

_SECRET_PATH = DB_PATH.parent / ".secret"


def _load_secret() -> bytes:
    env = os.environ.get("APP_SECRET")
    if env:
        return env.encode()
    if _SECRET_PATH.exists():
        return _SECRET_PATH.read_text().strip().encode()
    _SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_hex(32)
    _SECRET_PATH.write_text(secret)
    return secret.encode()


_SECRET = _load_secret()

# ---------- 密码 ----------


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt}${digest}"


def _is_legacy_sha256(stored: str) -> bool:
    return len(stored) == 64 and all(c in "0123456789abcdef" for c in stored)


def verify_password(user: User, password: str) -> bool:
    """校验密码；旧格式校验通过后由调用方决定是否升级存储。"""
    stored = user.password_hash or ""
    if not stored:
        return False
    if stored.startswith("pbkdf2$"):
        try:
            _, iters, salt, digest = stored.split("$", 3)
            calc = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), bytes.fromhex(salt), int(iters)
            ).hex()
            return hmac.compare_digest(calc, digest)
        except (ValueError, TypeError):
            return False
    if _is_legacy_sha256(stored):
        return hmac.compare_digest(
            stored, hashlib.sha256(password.encode()).hexdigest()
        )
    return False


def needs_password_upgrade(user: User) -> bool:
    stored = user.password_hash or ""
    return bool(stored) and not stored.startswith("pbkdf2$")

# ---------- 令牌 ----------


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(payload: str) -> str:
    return hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()[:32]


def make_token(user: User, *, now: Optional[int] = None) -> str:
    expiry = int(now if now is not None else time.time()) + TOKEN_TTL_SECONDS
    payload = f"{user.id}:{expiry}"
    return TOKEN_PREFIX + _b64e(f"{payload}:{_sign(payload)}".encode())


def parse_token(token: str, *, now: Optional[int] = None) -> Optional[int]:
    """校验签名与过期，返回 user_id；任何不符即 None。"""
    if not token.startswith(TOKEN_PREFIX):
        return None
    try:
        raw = _b64d(token[len(TOKEN_PREFIX) :]).decode()
        user_id_str, expiry_str, sig = raw.split(":", 2)
        payload = f"{user_id_str}:{expiry_str}"
        if not hmac.compare_digest(sig, _sign(payload)):
            return None
        if int(expiry_str) < int(now if now is not None else time.time()):
            return None
        return int(user_id_str)
    except Exception:
        return None

# ---------- FastAPI 依赖 ----------


def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> User:
    """强认证：Bearer 令牌验签 + 从 DB 取用户（角色以 DB 为准）。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    user_id = parse_token(authorization[7:])
    if user_id is None:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if getattr(user, "status", "正常") != "正常":
        raise HTTPException(status_code=401, detail="账号状态异常，请重新登录")
    return user


def get_operator_id(current_user: User = Depends(get_current_user)) -> int:
    return current_user.id


def require_role(user: User, allowed: tuple[str, ...]) -> None:
    if (user.role or "") not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"权限不足：需要「{'/'.join(allowed)}」角色，当前为「{user.role or '无'}」",
        )
