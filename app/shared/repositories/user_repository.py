import logging

from app.shared.core.config import settings
from app.shared.database.mongo import get_mongo_client

logger = logging.getLogger(__name__)


class UserRepository:
    @staticmethod
    async def ensure_indexes() -> None:
        """Enforce email uniqueness at the database level.

        The signup flow also checks for an existing email before inserting,
        but that check-then-insert is racy under concurrent requests — this
        index is the actual guarantee; the pre-check just gives a fast,
        friendly 409 in the common case.
        """
        client = get_mongo_client()
        db = client[settings.mongodb_db_name]
        await db["users"].create_index("email", unique=True)

    @staticmethod
    async def create_user(doc: dict) -> None:
        client = get_mongo_client()
        db = client[settings.mongodb_db_name]
        collection = db["users"]
        await collection.insert_one(doc)
        logger.info(f"[UserRepository] Created user {doc['id']}")

    @staticmethod
    async def get_by_email(email: str) -> dict | None:
        client = get_mongo_client()
        db = client[settings.mongodb_db_name]
        collection = db["users"]
        return await collection.find_one({"email": email})

    @staticmethod
    async def get_by_id(user_id: str) -> dict | None:
        client = get_mongo_client()
        db = client[settings.mongodb_db_name]
        collection = db["users"]
        return await collection.find_one({"id": user_id})

    @staticmethod
    async def update_password(user_id: str, password_hash: str) -> None:
        client = get_mongo_client()
        db = client[settings.mongodb_db_name]
        collection = db["users"]
        await collection.update_one(
            {"id": user_id},
            {"$set": {"password_hash": password_hash}}
        )
        logger.info(f"[UserRepository] Updated password for user {user_id}")

    @staticmethod
    async def update_profile(user_id: str, date_of_birth: str | None = None, gender: str | None = None, role: str | None = None, phone: str | None = None) -> None:
        client = get_mongo_client()
        db = client[settings.mongodb_db_name]
        collection = db["users"]
        
        updates = {}
        if date_of_birth is not None:
            updates["date_of_birth"] = date_of_birth
        if gender is not None:
            updates["gender"] = gender
        if role is not None:
            updates["role"] = role
        if phone is not None:
            updates["phone"] = phone
            
        if updates:
            await collection.update_one({"id": user_id}, {"$set": updates})
            logger.info(f"[UserRepository] Updated profile for user {user_id}")
