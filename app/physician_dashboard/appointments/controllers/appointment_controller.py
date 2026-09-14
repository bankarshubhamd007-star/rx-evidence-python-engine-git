from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel
from app.shared.models.schemas import AppointmentCreate, AppointmentResponse, RescheduleRequest, RescheduleRequestCreate
from app.shared.repositories.appointment_repository import AppointmentRepository

router = APIRouter(prefix="/v1/appointments", tags=["appointments"])


class StatusUpdate(BaseModel):
    status: str


@router.post("", response_model=AppointmentResponse)
async def create_appointment(data: AppointmentCreate):
    try:
        # Default doctor_id if not provided
        if not data.doctor_id:
            data.doctor_id = "doctor-123"
        return await AppointmentRepository.create_appointment(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[AppointmentResponse])
async def get_appointments(limit: int = 50):
    try:
        return await AppointmentRepository.get_all_appointments(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{apt_id}/status", response_model=AppointmentResponse)
async def update_appointment_status(apt_id: str, update_data: StatusUpdate):
    try:
        res = await AppointmentRepository.update_appointment_status(apt_id, update_data.status)
        if not res:
            raise HTTPException(status_code=404, detail="Appointment not found")
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{apt_id}/reschedule", response_model=RescheduleRequest)
async def create_reschedule_request(apt_id: str, req_data: RescheduleRequestCreate):
    try:
        req_data.appointment_id = apt_id
        res = await AppointmentRepository.create_reschedule_request(req_data)
        if not res:
            raise HTTPException(status_code=500, detail="Failed to create reschedule request")
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reschedule/all", response_model=List[RescheduleRequest])
async def get_all_reschedule_requests(limit: int = 50):
    try:
        return await AppointmentRepository.get_all_reschedule_requests(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RescheduleStatusUpdate(BaseModel):
    status: str
    new_time: str
    new_date: str


@router.patch("/reschedule/{req_id}/approve", response_model=RescheduleRequest)
async def approve_reschedule_request(req_id: str, update_data: RescheduleStatusUpdate):
    try:
        req = await AppointmentRepository.update_reschedule_request_status(req_id, update_data.status)
        if not req:
            raise HTTPException(status_code=404, detail="Reschedule request not found")
        
        # Also update the actual appointment
        await AppointmentRepository.update_appointment_time(req.appointment_id, update_data.new_time, update_data.new_date)
        
        return req
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
