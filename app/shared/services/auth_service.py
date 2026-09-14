from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.shared.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def create_reset_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "purpose": "reset_password",
        "iat": now,
        "exp": now + timedelta(minutes=15), # 15 min expiry
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def decode_reset_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != "reset_password":
            raise ValueError("Invalid token purpose")
        return payload["sub"]
    except jwt.PyJWTError:
        raise ValueError("Invalid or expired token")

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


import httpx
from fastapi import HTTPException, status

async def verify_google_token(token: str) -> dict:
    """Verifies a Google OAuth access token and returns the user profile."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Google token"
            )
            
        return response.json()
