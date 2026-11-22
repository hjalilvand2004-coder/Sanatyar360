import uuid
from datetime import datetime, timedelta, timezone

import argon2
import jwt

from .config import settings

_hasher = argon2.PasswordHasher()  # Argon2id (default params)


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except argon2.exceptions.VerifyMismatchError:
        return False


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def decode_token_payload(token: str) -> dict | None:
    """خواندن payload توکن سامانه مادر (بدون احراز امضا — امضا در Token Endpoint بررسی می‌شود)."""
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return None


def verify_hmac_token(token: str, secret: str) -> dict | None:
    """اعتبارسنجی توکن JWT صادرشده مرکز SSO/سامانه مادر با کلید مشترک (مدل سبک ?sso_token=).

    امضای HS256/384/512 و انقضا بررسی می‌شود؛ audience بررسی نمی‌شود (توکن‌های بین‌سامانه‌ای).
    """
    try:
        return jwt.decode(token, secret, algorithms=["HS256", "HS384", "HS512"],
                          options={"verify_aud": False})
    except jwt.PyJWTError:
        return None
