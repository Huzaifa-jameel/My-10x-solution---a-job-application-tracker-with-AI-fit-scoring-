"""Password hashing and JWT issuance.

Nothing here is hand-rolled: bcrypt does the hashing, python-jose does the
signing. The only judgement calls are the token lifetime and the 72-byte
password ceiling, both of which are explained below.
"""

import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt hashes at most 72 bytes and silently ignores everything after that,
# which would make two different long passwords interchangeable. The register
# schema rejects anything longer rather than letting that happen quietly.
BCRYPT_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: uuid.UUID) -> str:
    """Sign a JWT whose subject is the user id."""
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID | None:
    """Return the user id from a valid token, or None.

    An expired or tampered token is an ordinary outcome, not an exception to
    propagate - the caller turns it into a 401.
    """
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return uuid.UUID(claims["sub"])
    except (JWTError, KeyError, ValueError):
        return None
