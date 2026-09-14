import os

# Must run before any `app.*` import, since Settings() is instantiated at
# module import time in app/shared/core/config.py and requires these.
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB_NAME", "test_db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only")

import pytest
from mongomock_motor import AsyncMongoMockClient


@pytest.fixture
def mock_mongo_client() -> AsyncMongoMockClient:
    """A fresh in-memory Mongo client, isolated per test."""
    return AsyncMongoMockClient()


@pytest.fixture
def patch_mongo(monkeypatch, mock_mongo_client):
    """Patch a module's `get_mongo_client` to return the mock client.

    Usage: patch_mongo("app.shared.repositories.user_repository")
    """
    def _patch(module_path: str):
        monkeypatch.setattr(f"{module_path}.get_mongo_client", lambda: mock_mongo_client)
        return mock_mongo_client
    return _patch
