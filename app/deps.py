from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .db import get_db
from .auth import get_current_user, require_authenticated_user, require_role
from .models import User


def db_session_dep() -> Generator[Session, None, None]:
    yield from get_db()


def current_user_dep(
    request: Request,
    db: Session = Depends(db_session_dep),
) -> User | None:
    return get_current_user(request, db)


def authenticated_user_dep(
    request: Request,
    db: Session = Depends(db_session_dep),
) -> User:
    return require_authenticated_user(request, db)


def role_required_dep(*roles: str):
    def _dep(
        request: Request,
        db: Session = Depends(db_session_dep),
    ) -> User:
        return require_role(request, db, list(roles))

    return _dep
