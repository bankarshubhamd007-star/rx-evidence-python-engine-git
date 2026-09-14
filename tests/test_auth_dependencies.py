import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import COOKIE_NAME, get_current_user, require_role
from app.shared.models.schemas import UserRole
from app.shared.services.auth_service import create_access_token


@pytest.fixture(autouse=True)
def _mongo(patch_mongo):
    patch_mongo("app.shared.repositories.user_repository")


@pytest.fixture
def app_with_routes():
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(user=Depends(get_current_user)):
        return {"id": user.id, "role": user.role}

    @app.get("/physician-only")
    async def physician_only(user=Depends(require_role(UserRole.PHYSICIAN))):
        return {"id": user.id}

    return app


async def _seed_user(user_id="user-123", role="physician"):
    from app.shared.repositories.user_repository import UserRepository
    await UserRepository.create_user({
        "id": user_id,
        "email": "vance@clinic.org",
        "password_hash": "hashed",
        "full_name": "Dr. Vance",
        "phone": None,
        "role": role,
        "created_at": 1000.0,
    })


async def test_get_current_user_no_cookie_is_401(app_with_routes):
    client = TestClient(app_with_routes)
    res = client.get("/whoami")
    assert res.status_code == 401


async def test_get_current_user_valid_cookie_returns_user(app_with_routes):
    await _seed_user()
    token = create_access_token(user_id="user-123", role="physician")
    client = TestClient(app_with_routes)
    client.cookies.set(COOKIE_NAME, token)
    res = client.get("/whoami")
    assert res.status_code == 200
    assert res.json() == {"id": "user-123", "role": "physician"}


async def test_get_current_user_invalid_token_is_401(app_with_routes):
    client = TestClient(app_with_routes)
    client.cookies.set(COOKIE_NAME, "not-a-real-token")
    res = client.get("/whoami")
    assert res.status_code == 401


async def test_require_role_matching_role_allows(app_with_routes):
    await _seed_user(role="physician")
    token = create_access_token(user_id="user-123", role="physician")
    client = TestClient(app_with_routes)
    client.cookies.set(COOKIE_NAME, token)
    res = client.get("/physician-only")
    assert res.status_code == 200


async def test_require_role_mismatched_role_is_403(app_with_routes):
    await _seed_user(user_id="user-456", role="patient")
    token = create_access_token(user_id="user-456", role="patient")
    client = TestClient(app_with_routes)
    client.cookies.set(COOKIE_NAME, token)
    res = client.get("/physician-only")
    assert res.status_code == 403
