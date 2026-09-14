from motor.motor_asyncio import AsyncIOMotorClient
from app.shared.core.config import settings

# Initialize the MongoDB client globally so it reuses connection pools
_client: AsyncIOMotorClient | None = None

import certifi

def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            settings.mongodb_uri, 
            tls=True,
            tlsAllowInvalidCertificates=True
        )
    return _client
