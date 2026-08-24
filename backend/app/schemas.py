from datetime import datetime, time
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- Auth ----------

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    phone: Optional[str] = None
    role: Literal["customer", "business_owner"] = "customer"


class UserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Businesses / Services ----------

class CategoryOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class BusinessCreate(BaseModel):
    name: str
    category_id: Optional[int] = None
    description: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    description: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class BusinessOut(BaseModel):
    id: int
    name: str
    category_id: Optional[int] = None
    description: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class ServiceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    duration_minutes: int = Field(gt=0, le=600)
    price: float = Field(ge=0)


class ServiceOut(BaseModel):
    id: int
    business_id: int
    name: str
    description: Optional[str] = None
    duration_minutes: int
    price: float
    is_active: bool

    class Config:
        from_attributes = True


class StaffCreate(BaseModel):
    full_name: str


class StaffOut(BaseModel):
    id: int
    business_id: int
    full_name: str

    class Config:
        from_attributes = True


class WorkingHoursCreate(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time


class WorkingHoursOut(BaseModel):
    id: int
    staff_id: int
    day_of_week: int
    start_time: time
    end_time: time

    class Config:
        from_attributes = True


# ---------- Appointments ----------

class AppointmentCreate(BaseModel):
    service_id: int
    staff_id: int
    start_time: datetime


class AppointmentOut(BaseModel):
    id: int
    customer_id: int
    business_id: int
    service_id: int
    staff_id: int
    start_time: datetime
    end_time: datetime
    status: str

    class Config:
        from_attributes = True


class AppointmentStatusUpdate(BaseModel):
    status: Literal["confirmed", "completed", "no_show", "cancelled"]


class CustomerAppointmentOut(BaseModel):
    id: int
    business_name: str
    service_name: str
    staff_name: str
    start_time: datetime
    end_time: datetime
    status: str
    has_review: bool


# ---------- Reviews ----------

class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1000)


class ReviewOut(BaseModel):
    id: int
    appointment_id: int
    rating: int
    comment: Optional[str] = None
    created_at: datetime
    customer_name: str


class OwnerAppointmentOut(BaseModel):
    id: int
    start_time: datetime
    end_time: datetime
    status: str
    cancellation_reason: Optional[str] = None
    customer_name: str
    customer_email: str
    service_name: str
    staff_name: str


# ---------- Notifications ----------

class NotificationOut(BaseModel):
    id: int
    appointment_id: Optional[int] = None
    type: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Admin ----------

class UserRoleUpdate(BaseModel):
    role: Literal["customer", "business_owner", "admin"]


class BusinessStatusUpdate(BaseModel):
    status: Literal["pending", "active", "suspended"]


class AdminBusinessOut(BaseModel):
    id: int
    name: str
    status: str
    owner_name: str
    owner_email: str
    category_name: Optional[str] = None


# ---------- Agent chat ----------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AgentChatRequest(BaseModel):
    conversation: list[ChatMessage]


class ProposedAppointmentOut(BaseModel):
    service_id: int
    staff_id: int
    business_id: int
    start_time: datetime
    end_time: datetime
    service_name: str
    business_name: str
    staff_name: str
    price: float


class AgentChatResponse(BaseModel):
    reply: str
    status: Literal["clarify", "proposed", "failed"]
    proposal: Optional[ProposedAppointmentOut] = None
    conversation: list[ChatMessage]
