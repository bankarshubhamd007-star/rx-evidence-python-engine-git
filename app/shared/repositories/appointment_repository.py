import logging
from pymongo import ReturnDocument
from app.shared.core.config import settings
from app.shared.models.schemas import AppointmentCreate, AppointmentResponse, RescheduleRequest, RescheduleRequestCreate
from app.shared.database.mongo import get_mongo_client
import time
import uuid

logger = logging.getLogger(__name__)

class AppointmentRepository:
    @staticmethod
    async def create_appointment(data: AppointmentCreate) -> AppointmentResponse:
        try:
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            collection = db["appointments"]
            
            apt_id = str(uuid.uuid4())
            document = data.model_dump()
            document["id"] = apt_id
            document["created_at"] = time.time()
            
            if "status" not in document or not document["status"]:
                document["status"] = "Pending"
                
            await collection.insert_one(document)
            logger.info(f"[AppointmentRepository] Created appointment {apt_id}")
            
            return AppointmentResponse(**document)
            
        except Exception as e:
            logger.error(f"[AppointmentRepository] Failed to create appointment: {e}")
            raise e

    @staticmethod
    async def get_all_appointments(limit: int = 50) -> list[AppointmentResponse]:
        try:
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            collection = db["appointments"]
            
            cursor = collection.find({}).sort("created_at", -1).limit(limit)
            results = []
            async for doc in cursor:
                results.append(AppointmentResponse(**doc))
            return results
        except Exception as e:
            logger.error(f"[AppointmentRepository] Failed to get all appointments: {e}")
            return []

    @staticmethod
    async def update_appointment_status(apt_id: str, status: str) -> AppointmentResponse | None:
        try:
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            collection = db["appointments"]
            
            updated_doc = await collection.find_one_and_update(
                {"id": apt_id},
                {"$set": {"status": status}},
                return_document=ReturnDocument.AFTER
            )
            
            if updated_doc:
                logger.info(f"[AppointmentRepository] Updated status of {apt_id} to {status}")
                return AppointmentResponse(**updated_doc)
            return None
        except Exception as e:
            logger.error(f"[AppointmentRepository] Failed to update appointment status {apt_id}: {e}")
            return None

    @staticmethod
    async def create_reschedule_request(req_data: RescheduleRequestCreate) -> RescheduleRequest | None:
        try:
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            collection = db["reschedule_requests"]
            
            req_id = str(uuid.uuid4())
            document = req_data.model_dump()
            document["id"] = req_id
            document["requested_at"] = str(time.time())
            
            if "status" not in document or not document["status"]:
                document["status"] = "Pending Approval"
                
            await collection.insert_one(document)
            logger.info(f"[AppointmentRepository] Created reschedule request {req_id}")
            
            return RescheduleRequest(**document)
        except Exception as e:
            logger.error(f"[AppointmentRepository] Failed to create reschedule request: {e}")
            return None

    @staticmethod
    async def get_all_reschedule_requests(limit: int = 50) -> list[RescheduleRequest]:
        try:
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            collection = db["reschedule_requests"]
            
            cursor = collection.find({}).sort("requestedAt", -1).limit(limit)
            results = []
            async for doc in cursor:
                results.append(RescheduleRequest(**doc))
            return results
        except Exception as e:
            logger.error(f"[AppointmentRepository] Failed to get all reschedule requests: {e}")
            return []

    @staticmethod
    async def update_reschedule_request_status(req_id: str, status: str) -> RescheduleRequest | None:
        try:
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            collection = db["reschedule_requests"]
            
            updated_doc = await collection.find_one_and_update(
                {"id": req_id},
                {"$set": {"status": status}},
                return_document=ReturnDocument.AFTER
            )
            
            if updated_doc:
                logger.info(f"[AppointmentRepository] Updated status of reschedule request {req_id} to {status}")
                return RescheduleRequest(**updated_doc)
            return None
        except Exception as e:
            logger.error(f"[AppointmentRepository] Failed to update reschedule request status {req_id}: {e}")
            return None

    @staticmethod
    async def update_appointment_time(apt_id: str, new_time: str, new_date: str) -> AppointmentResponse | None:
        try:
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            collection = db["appointments"]
            
            updated_doc = await collection.find_one_and_update(
                {"id": apt_id},
                {"$set": {"timeSlot": new_time, "date": new_date}},
                return_document=ReturnDocument.AFTER
            )
            
            if updated_doc:
                logger.info(f"[AppointmentRepository] Updated time of {apt_id} to {new_date} {new_time}")
                return AppointmentResponse(**updated_doc)
            return None
        except Exception as e:
            logger.error(f"[AppointmentRepository] Failed to update appointment time {apt_id}: {e}")
            return None
