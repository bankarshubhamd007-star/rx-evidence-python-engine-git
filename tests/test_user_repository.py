import pytest

from app.shared.repositories.user_repository import UserRepository


@pytest.fixture(autouse=True)
def _mongo(patch_mongo):
    patch_mongo("app.shared.repositories.user_repository")


def _user_doc(email="vance@clinic.org"):
    return {
        "id": "user-123",
        "email": email,
        "password_hash": "hashed",
        "full_name": "Dr. Vance",
        "phone": "+1-555-0192",
        "role": "physician",
        "created_at": 1000.0,
    }


async def test_create_and_get_by_email():
    await UserRepository.create_user(_user_doc())
    found = await UserRepository.get_by_email("vance@clinic.org")
    assert found is not None
    assert found["id"] == "user-123"
    assert found["full_name"] == "Dr. Vance"


async def test_get_by_email_not_found_returns_none():
    found = await UserRepository.get_by_email("nobody@nowhere.org")
    assert found is None


async def test_get_by_id():
    await UserRepository.create_user(_user_doc())
    found = await UserRepository.get_by_id("user-123")
    assert found is not None
    assert found["email"] == "vance@clinic.org"


async def test_get_by_id_not_found_returns_none():
    found = await UserRepository.get_by_id("does-not-exist")
    assert found is None
