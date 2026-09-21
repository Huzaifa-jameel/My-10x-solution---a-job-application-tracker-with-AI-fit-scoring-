"""The dependency that turns a Bearer token into a User."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.db import get_db
from app.models.user import User

# HTTPBearer rather than OAuth2PasswordBearer: the API takes a JSON login body,
# and this still gives /docs an Authorize button to paste a token into.
bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORISED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _UNAUTHORISED

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise _UNAUTHORISED

    user = db.get(User, user_id)
    if user is None:
        # The token is valid but the account is gone. Same answer either way.
        raise _UNAUTHORISED
    return user
