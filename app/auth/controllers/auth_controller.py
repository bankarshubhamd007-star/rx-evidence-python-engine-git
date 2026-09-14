import time
import uuid
<<<<<<< HEAD
=======
from datetime import datetime, timezone
>>>>>>> python-engine

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pymongo.errors import DuplicateKeyError

from app.auth.dependencies import COOKIE_NAME, get_current_user
from app.shared.core.config import settings
from app.shared.models.schemas import AnalysisResult, AuthResponse, ForgotPasswordRequest, GoogleAuthRequest, LoginRequest, ResetPasswordRequest, SignupRequest, UpdateProfileRequest, UserPublic, UserRole
from app.shared.repositories.mongo_repository import MongoRepository
from app.shared.repositories.user_repository import UserRepository
from app.shared.services.auth_service import create_access_token, create_reset_token, decode_reset_token, hash_password, verify_google_token, verify_password

router = APIRouter()

COOKIE_MAX_AGE = settings.jwt_expire_minutes * 60


def _set_session_cookie(response: Response, user_id: str, role: str) -> None:
    token = create_access_token(user_id=user_id, role=role)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="none",
        secure=True,
        max_age=COOKIE_MAX_AGE,
        path="/",
    )


def _to_user_public(doc: dict) -> UserPublic:
    return UserPublic(
        id=doc["id"],
        full_name=doc["full_name"],
        email=doc["email"],
        phone=doc.get("phone"),
        role=doc["role"],
        date_of_birth=doc.get("date_of_birth"),
        gender=doc.get("gender"),
        subscription_tier=doc.get("subscription_tier", "free"),
        payment_provider_id=doc.get("payment_provider_id"),
        premium_features_enabled=doc.get("premium_features_enabled", False),
    )


@router.post("/signup", response_model=AuthResponse)
async def signup(req: SignupRequest, response: Response):
    existing = await UserRepository.get_by_email(req.email)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user_doc = {
        "id": uuid.uuid4().hex,
        "email": req.email,
        "password_hash": hash_password(req.password),
        "full_name": req.full_name,
        "phone": req.phone,
        "role": req.role.value,
<<<<<<< HEAD
        "created_at": time.time(),
=======
        "created_at": datetime.now(timezone.utc).isoformat(),
>>>>>>> python-engine
    }
    try:
        await UserRepository.create_user(user_doc)
    except DuplicateKeyError:
        # The get_by_email check above is racy under concurrent signups;
        # the unique index is the real guarantee, this is the backstop.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    _set_session_cookie(response, user_doc["id"], user_doc["role"])
    return AuthResponse(user=_to_user_public(user_doc))


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, response: Response):
    user = await UserRepository.get_by_email(req.email)
    if user is None or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    _set_session_cookie(response, user["id"], user["role"])
    return AuthResponse(user=_to_user_public(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")


@router.post("/google", response_model=AuthResponse)
async def google_login(req: GoogleAuthRequest, response: Response):
    profile = await verify_google_token(req.token)
    email = profile.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Google token did not provide an email")
        
    user = await UserRepository.get_by_email(email)
    
    if not user:
        # Create a new user from Google profile
        user = {
            "id": uuid.uuid4().hex,
            "email": email,
            "password_hash": "", # No password for Google SSO users
            "full_name": profile.get("name", "Unknown"),
            "phone": None,
            "role": UserRole.PATIENT.value, # Default role
<<<<<<< HEAD
            "created_at": time.time(),
=======
            "created_at": datetime.now(timezone.utc).isoformat(),
>>>>>>> python-engine
            "date_of_birth": None,
            "gender": None,
            "subscription_tier": "free",
            "payment_provider_id": None,
            "premium_features_enabled": False,
        }
        await UserRepository.create_user(user)

    _set_session_cookie(response, user["id"], user["role"])
    return AuthResponse(user=_to_user_public(user))


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(req: ForgotPasswordRequest):
    user = await UserRepository.get_by_email(req.email)
    if not user:
        # We don't want to leak whether an email exists, so we always return 200 OK.
        return {"message": "If an account with that email exists, a password reset link has been sent."}
        
    reset_token = create_reset_token(user["id"])
    
    # Normally we would send an email here with a link like:
    # https://your-dashboard.com/reset-password?token={reset_token}
    # For now, we will simulate sending the email by logging it.
    print(f"EMAIL SIMULATION: Send password reset link to {req.email}: http://localhost:3000/reset-password?token={reset_token}")
    
    return {"message": "If an account with that email exists, a password reset link has been sent."}

@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(req: ResetPasswordRequest):
    try:
        user_id = decode_reset_token(req.token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        
    user = await UserRepository.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    new_hash = hash_password(req.new_password)
    await UserRepository.update_password(user_id, new_hash)
    
    return {"message": "Password successfully reset."}

@router.get("/me", response_model=AuthResponse)
async def me(current_user: UserPublic = Depends(get_current_user)):
    return AuthResponse(user=current_user)

@router.patch("/me", response_model=AuthResponse)
async def update_me(req: UpdateProfileRequest, current_user: UserPublic = Depends(get_current_user)):
    role_str = req.role.value if req.role else None
    await UserRepository.update_profile(
        user_id=current_user.id,
        date_of_birth=req.date_of_birth,
        gender=req.gender,
        role=role_str,
        phone=req.phone
    )
    user = await UserRepository.get_by_id(current_user.id)
    return AuthResponse(user=_to_user_public(user))

@router.get("/me/claims", response_model=list[AnalysisResult])
async def get_my_claims(
    limit: int = 50, 
    current_user: UserPublic = Depends(get_current_user)
):
    """Fetches the user's personal analyzed claims history."""
    return await MongoRepository.get_user_claims(current_user.id, limit=limit)
