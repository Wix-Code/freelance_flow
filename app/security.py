
import os
import jwt
import hashlib
import secrets

from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app import models
from app.database import get_db


load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

if len(SECRET_KEY) < 32:
    raise RuntimeError(
        "Set JWT_SECRET_KEY in your .env file"
    )

ALGORITHM = "HS256"

ACCESS_MINUTES = 15
REFRESH_DAYS = 7
RESET_MINUTES = 20

password_hasher = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


def utcnow():
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    return password_hasher.verify(
        plain_password,
        hashed_password
    )


def digest_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(user: models.User):
    now = utcnow()

    payload = {
        "sub": str(user.id),
        "type": "access",
        "ver": user.token_version,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_MINUTES),
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def credentials_error():
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={
                "require": ["sub", "iat", "exp"]
            }
        )

        if payload.get("type") != "access":
            raise credentials_error()

        user_id = int(payload["sub"])
        token_version = payload.get("ver")

    except (InvalidTokenError, ValueError, TypeError, KeyError):
        raise credentials_error() from None

    user = db.get(models.User, user_id)

    if not user:
        raise credentials_error()

    if not user.is_active:
        raise credentials_error()

    if user.token_version != token_version:
        raise credentials_error()

    return user
