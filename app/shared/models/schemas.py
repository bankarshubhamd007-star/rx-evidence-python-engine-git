from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Verdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    MISLEADING = "MISLEADING"
    LIKELY_FALSE = "LIKELY_FALSE"
    FALSE = "FALSE"
    UNVERIFIABLE = "UNVERIFIABLE"
    OPINION = "OPINION"


class EvidenceSource(CamelModel):
    title: str
    publisher: str | None = None
    url: str | None = None
    stance: Literal["supports", "contradicts", "neutral"] | None = None
    relevance: float | None = Field(default=None, ge=0, le=1)


class AnalyzeRequest(CamelModel):
    claim: str = Field(min_length=1, max_length=2000)
    context: str | None = Field(default=None, max_length=4000)
    url: str | None = None
    title: str | None = None
    language: str = "en"
    accuracy_level: Literal["low", "medium", "high"] = "medium"


class AnalysisResult(CamelModel):
    id: str
    claim: str
    confidence: float = Field(ge=0, le=1)
    is_accurate: bool = False
    summary: str
    key_points: list[str]
    evidence: list[EvidenceSource]
    created_at: float
    accuracy_level: Literal["low", "medium", "high"] = "medium"


class TrendResponse(AnalysisResult):
    count: int


class BatchAnalyzeRequest(CamelModel):
    claims: list[str] = Field(min_length=1, max_length=50)
    accuracy_level: Literal["low", "medium", "high"] = "medium"


class BatchAnalyzeResponse(CamelModel):
    results: list[AnalysisResult]


class FeedbackVote(str, Enum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"


class FeedbackRequest(CamelModel):
    analysis_id: str
    vote: FeedbackVote
    reason: str | None = None


class FeedbackAck(CamelModel):
    status: Literal["received"] = "received"


class HealthStatus(CamelModel):
    status: Literal["ok"] = "ok"
    version: str


class AppointmentCreate(CamelModel):
    patient_name: str
    age: int
    gender: str
    reason_for_visit: str
    date: str
    time_slot: str
    status: str | None = None
    doctor_id: str | None = None


class AppointmentResponse(AppointmentCreate):
    id: str
    created_at: float


class RescheduleRequestCreate(CamelModel):
    appointment_id: str
    patient_name: str
    age: int
    gender: str
    current_slot: str
    requested_slot: str
    patient_reason: str
    status: str | None = None


class RescheduleRequest(RescheduleRequestCreate):
    id: str
    requested_at: str


class UserRole(str, Enum):
    PHYSICIAN = "physician"
    PATIENT = "patient"


class SignupRequest(CamelModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str | None = None
    password: str = Field(min_length=8, max_length=72)
    role: UserRole


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserPublic(CamelModel):
    id: str
    full_name: str
    email: str
    phone: str | None = None
    role: UserRole
    date_of_birth: str | None = None
    gender: str | None = None
    subscription_tier: str = "free"
    payment_provider_id: str | None = None
    premium_features_enabled: bool = False


class AuthResponse(CamelModel):
    user: UserPublic


class GoogleAuthRequest(CamelModel):
    token: str


class ForgotPasswordRequest(CamelModel):
    email: EmailStr


class ResetPasswordRequest(CamelModel):
    token: str
    new_password: str = Field(min_length=8, max_length=72)


class UpdateProfileRequest(CamelModel):
    date_of_birth: str | None = None
    gender: str | None = None
    role: UserRole | None = None
    phone: str | None = None
