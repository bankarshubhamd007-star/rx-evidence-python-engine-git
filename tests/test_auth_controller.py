import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.controllers import auth_controller
from app.auth.dependencies import COOKIE_NAME


@pytest.fixture(autouse=True)
def _mongo(patch_mongo):
    patch_mongo("app.shared.repositories.user_repository")


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(auth_controller.router, prefix="/v1/auth")
    return TestClient(app)


def _signup_payload(email="vance@clinic.org", role="physician"):
    return {
        "fullName": "Dr. Vance",
        "email": email,
        "phone": "+1-555-0192",
        "password": "secretpass1",
        "role": role,
    }


def test_signup_creates_user_and_sets_cookie(client):
    res = client.post("/v1/auth/signup", json=_signup_payload())
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["email"] == "vance@clinic.org"
    assert body["user"]["role"] == "physician"
    assert COOKIE_NAME in res.cookies


def test_signup_duplicate_email_is_409(client):
    client.post("/v1/auth/signup", json=_signup_payload())
    res = client.post("/v1/auth/signup", json=_signup_payload())
    assert res.status_code == 409


def test_login_correct_credentials_sets_cookie(client):
    client.post("/v1/auth/signup", json=_signup_payload())
    res = client.post("/v1/auth/login", json={"email": "vance@clinic.org", "password": "secretpass1"})
    assert res.status_code == 200
    assert COOKIE_NAME in res.cookies


def test_login_wrong_password_is_401(client):
    client.post("/v1/auth/signup", json=_signup_payload())
    res = client.post("/v1/auth/login", json={"email": "vance@clinic.org", "password": "wrongpass"})
    assert res.status_code == 401


def test_login_unknown_email_is_401(client):
    res = client.post("/v1/auth/login", json={"email": "nobody@nowhere.org", "password": "whatever1"})
    assert res.status_code == 401


def test_me_without_cookie_is_401(client):
    res = client.get("/v1/auth/me")
    assert res.status_code == 401


def test_me_after_login_returns_current_user(client):
    client.post("/v1/auth/signup", json=_signup_payload())
    res = client.get("/v1/auth/me")
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "vance@clinic.org"


def test_logout_clears_cookie_and_me_then_401(client):
    client.post("/v1/auth/signup", json=_signup_payload())
    res = client.post("/v1/auth/logout")
    assert res.status_code == 204
    res2 = client.get("/v1/auth/me")
    assert res2.status_code == 401
