
import os
import smtplib
import ssl

from datetime import timedelta, timezone
from email.message import EmailMessage
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app import auth_schemas as schemas
from app.database import get_db
from app.security import (
    REFRESH_DAYS,
    RESET_MINUTES,
    create_access_token,
    digest_token,
    get_current_user,
    hash_password,
    new_opaque_token,
    utcnow,
    verify_password,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

Db = Annotated[Session, Depends(get_db)]

CurrentUser = Annotated[
    models.User,
    Depends(get_current_user)
]


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_expired(expiry):
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry <= utcnow()


def issue_token_pair(
    db: Session,
    user: models.User
):
    raw_refresh_token = new_opaque_token()

    refresh_token = models.RefreshToken(
        user_id=user.id,
        token_hash=digest_token(raw_refresh_token),
        expires_at=utcnow() + timedelta(
            days=REFRESH_DAYS
        )
    )

    db.add(refresh_token)
    db.commit()

    return schemas.TokenResponse(
        access_token=create_access_token(user),
        refresh_token=raw_refresh_token
    )


def revoke_all_sessions(
    db: Session,
    user: models.User
):
    db.execute(
        update(models.RefreshToken)
        .where(models.RefreshToken.user_id == user.id)
        .values(revoked=True)
    )

    user.token_version += 1


def send_password_reset(email: str, token: str):
    if os.getenv("DEV_PRINT_RESET_LINK") == "1":
        print(
            f"DEV ONLY password reset token "
            f"for {email}: {token}"
        )
        return

    required = [
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "SMTP_FROM",
        "FRONTEND_RESET_URL",
    ]

    if any(not os.getenv(key) for key in required):
        raise RuntimeError(
            "Password reset email is not configured"
        )

    message = EmailMessage()
    message["Subject"] = "Reset your FreelanceFlow password"
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = email

    message.set_content(
        f"Open {os.environ['FRONTEND_RESET_URL']} "
        f"and enter this reset token: {token}\n"
        f"Expires in {RESET_MINUTES} minutes."
    )

    with smtplib.SMTP(
        os.environ["SMTP_HOST"],
        int(os.environ["SMTP_PORT"]),
        timeout=10
    ) as smtp:
        smtp.starttls(
            context=ssl.create_default_context()
        )
        smtp.login(
            os.environ["SMTP_USER"],
            os.environ["SMTP_PASSWORD"]
        )
        smtp.send_message(message)


@router.post(
    "/register",
    response_model=schemas.UserResponse,
    status_code=201
)
def register(
    payload: schemas.RegisterRequest,
    db: Db
):
    email = normalize_email(str(payload.email))

    existing_user = db.scalar(
        select(models.User).where(
            models.User.email == email
        )
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    new_user = models.User(
        full_name=payload.full_name.strip(),
        email=email,
        password_hash=hash_password(payload.password)
    )

    db.add(new_user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        ) from None

    db.refresh(new_user)

    return new_user


@router.post(
    "/login",
    response_model=schemas.TokenResponse
)
def login(
    form: Annotated[
        OAuth2PasswordRequestForm,
        Depends()
    ],
    db: Db
):
    email = normalize_email(form.username)

    user = db.scalar(
        select(models.User).where(
            models.User.email == email
        )
    )

    if (
        not user
        or not verify_password(
            form.password,
            user.password_hash
        )
        or not user.is_active
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    return issue_token_pair(db, user)


@router.get(
    "/me",
    response_model=schemas.UserResponse
)
def get_profile(user: CurrentUser):
    return user


@router.post(
    "/refresh",
    response_model=schemas.TokenResponse
)
def refresh_token(
    payload: schemas.RefreshRequest,
    db: Db
):
    token = db.scalar(
        select(models.RefreshToken)
        .where(
            models.RefreshToken.token_hash
            == digest_token(payload.refresh_token)
        )
        .with_for_update()
    )

    if (
        not token
        or token.revoked
        or is_expired(token.expires_at)
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )

    user = db.get(models.User, token.user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Account unavailable"
        )

    token.revoked = True

    return issue_token_pair(db, user)

@router.post(
    "/logout",
    response_model=schemas.MessageResponse
)
def logout(
    payload: schemas.RefreshRequest,
    user: CurrentUser,
    db: Db
):
    token = db.scalar(
        select(models.RefreshToken).where(
            models.RefreshToken.token_hash
            == digest_token(payload.refresh_token),
            models.RefreshToken.user_id == user.id
        )
    )

    if token:
        token.revoked = True
        db.commit()

    return {
        "message": "Refresh session ended"
    }

@router.post(
    "/logout-all",
    response_model=schemas.MessageResponse
)
def logout_all(
    user: CurrentUser,
    db: Db
):
    revoke_all_sessions(db, user)

    db.commit()

    return {
        "message": "All sessions revoked"
    }


@router.post(
    "/change-password",
    response_model=schemas.MessageResponse
)
def change_password(
    payload: schemas.ChangePasswordRequest,
    user: CurrentUser,
    db: Db
):
    if not verify_password(
        payload.current_password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect"
        )

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different"
        )

    user.password_hash = hash_password(
        payload.new_password
    )

    revoke_all_sessions(db, user)

    db.commit()

    return {
        "message": "Password changed. Sign in again."
    }


@router.post(
    "/forgot-password",
    response_model=schemas.MessageResponse
)
def forgot_password(
    payload: schemas.ForgotPasswordRequest,
    db: Db
):
    user = db.scalar(
        select(models.User).where(
            models.User.email == normalize_email(
                str(payload.email)
            )
        )
    )

    generic_response = {
        "message": (
            "If this email is registered, "
            "reset instructions will be sent."
        )
    }

    if user and user.is_active:
        raw_token = new_opaque_token()

        reset_token = models.PasswordResetToken(
            user_id=user.id,
            token_hash=digest_token(raw_token),
            expires_at=utcnow() + timedelta(
                minutes=RESET_MINUTES
            )
        )

        db.add(reset_token)
        db.commit()

        try:
            send_password_reset(
                user.email,
                raw_token
            )
        except Exception:
            db.delete(reset_token)
            db.commit()

            raise HTTPException(
                status_code=503,
                detail="Password reset delivery unavailable"
            ) from None

    return generic_response


@router.post(
    "/reset-password",
    response_model=schemas.MessageResponse
)
def reset_password(
    payload: schemas.ResetPasswordRequest,
    db: Db
):
    reset_token = db.scalar(
        select(models.PasswordResetToken)
        .where(
            models.PasswordResetToken.token_hash
            == digest_token(payload.token)
        )
        .with_for_update()
    )

    if (
        not reset_token
        or reset_token.used
        or is_expired(reset_token.expires_at)
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token"
        )

    user = db.get(
        models.User,
        reset_token.user_id
    )

    if not user or not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token"
        )

    user.password_hash = hash_password(
        payload.new_password
    )

    reset_token.used = True

    revoke_all_sessions(db, user)

    db.commit()

    return {
        "message": "Password reset. Sign in again."
    }
