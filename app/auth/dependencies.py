from fastapi import Depends, HTTPException, Request, status
import jwt

from app.shared.models.schemas import UserPublic, UserRole
from app.shared.repositories.user_repository import UserRepository
from app.shared.services.auth_service import decode_access_token

COOKIE_NAME = "session"


async def get_current_user(request: Request) -> UserPublic:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    user = await UserRepository.get_by_id(payload["sub"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return UserPublic(
        id=user["id"],
        full_name=user["full_name"],
        email=user["email"],
        phone=user.get("phone"),
        role=user["role"],
        date_of_birth=user.get("date_of_birth"),
        gender=user.get("gender"),
        subscription_tier=user.get("subscription_tier", "free"),
        payment_provider_id=user.get("payment_provider_id"),
        premium_features_enabled=user.get("premium_features_enabled", False),
    )


async def get_current_user_optional(request: Request) -> UserPublic | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        return None

    user = await UserRepository.get_by_id(payload["sub"])
    if user is None:
        return None

    return UserPublic(
        id=user["id"],
        full_name=user["full_name"],
        email=user["email"],
        phone=user.get("phone"),
        role=user["role"],
        date_of_birth=user.get("date_of_birth"),
        gender=user.get("gender"),
        subscription_tier=user.get("subscription_tier", "free"),
        payment_provider_id=user.get("payment_provider_id"),
        premium_features_enabled=user.get("premium_features_enabled", False),
    )


def require_role(role: UserRole):
    async def _dependency(user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if user.role != role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return _dependency
