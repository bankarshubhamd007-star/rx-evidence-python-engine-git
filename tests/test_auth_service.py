import time

import jwt
import pytest

from app.shared.core.config import settings
from app.shared.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_produces_different_hash_each_time():
    h1 = hash_password("secretpass1")
    h2 = hash_password("secretpass1")
    assert h1 != h2
    assert h1 != "secretpass1"


def test_verify_password_correct():
    h = hash_password("secretpass1")
    assert verify_password("secretpass1", h) is True


def test_verify_password_incorrect():
    h = hash_password("secretpass1")
    assert verify_password("wrongpass", h) is False


def test_create_and_decode_access_token_round_trip():
    token = create_access_token(user_id="user-123", role="physician")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "physician"


def test_decode_access_token_rejects_bad_signature():
    token = jwt.encode(
        {"sub": "user-123", "role": "physician", "exp": time.time() + 60},
        "wrong-secret",
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_decode_access_token_rejects_expired_token():
    token = jwt.encode(
        {"sub": "user-123", "role": "physician", "exp": time.time() - 60},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)
