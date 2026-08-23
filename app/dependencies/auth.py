from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db
from app.models.user import User, UserRole
from app.services.auth_service import JWTError, decode_access_token

# auto_error=False so a MISSING token doesn't auto-raise 403; we handle it below
# and return 401 instead — "no/invalid credentials" is 401, "wrong role" is 403.
bearer_scheme = HTTPBearer(auto_error=False)

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None:
        raise _credentials_exc  # no Authorization header -> 401

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise _credentials_exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _credentials_exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _credentials_exc
    return user


def require_role(required: UserRole):
    async def _guard(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role != required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{required.value.capitalize()} access required",
            )
        return current_user

    return _guard


require_organizer = require_role(UserRole.organizer)
require_customer = require_role(UserRole.customer)
