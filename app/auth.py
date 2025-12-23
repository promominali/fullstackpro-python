from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, Response, HTTPException, status
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .models import User


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
serializer = URLSafeTimedSerializer(settings.secret_key)

SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # 7 days
BCRYPT_MAX_LENGTH = 72  # bcrypt only uses the first 72 bytes


def _truncate_for_bcrypt(password: str) -> str:
    """Ensure passwords passed to bcrypt are within its length limit.

    bcrypt ignores everything beyond 72 bytes; passlib raises an error instead.
    For this demo app, we simply truncate to 72 characters so very long
    passwords don't crash registration/login.
    """

    if len(password) <= BCRYPT_MAX_LENGTH:
        return password
    return password[:BCRYPT_MAX_LENGTH]


def hash_password(password: str) -> str:
    return pwd_context.hash(_truncate_for_bcrypt(password))



def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(_truncate_for_bcrypt(plain_password), hashed_password)

def create_session_token(user_id: int) -> str:
    return serializer.dumps({"user_id": user_id})


def get_user_id_from_token(token: str) -> Optional[int]:
    try:
        data = serializer.loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except SignatureExpired:
        return None
    except BadSignature:
        return None
    return int(data.get("user_id"))


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=False,  # set True when behind HTTPS in production
        samesite="lax",
        max_age=SESSION_MAX_AGE_SECONDS,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name)


def get_current_user(request: Request, db: Session) -> Optional[User]:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    user_id = get_user_id_from_token(token)
    if not user_id:
        return None
    return db.get(User, user_id)


def require_authenticated_user(request: Request, db: Session) -> User:
    user = get_current_user(request, db)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_role(request: Request, db: Session, roles: list[str]) -> User:
    user = require_authenticated_user(request, db)
    if user.is_superuser:
        return user
    user_roles = {role.name for role in user.roles}
    if not user_roles.intersection(set(roles)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return user
