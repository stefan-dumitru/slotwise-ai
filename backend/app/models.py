from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    DECIMAL,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(30))
    role = Column(Enum("customer", "business_owner", "admin", name="user_role"), nullable=False, default="customer")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    businesses = relationship("Business", back_populates="owner")
    appointments = relationship("Appointment", back_populates="customer")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

    businesses = relationship("Business", back_populates="category")


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"))
    name = Column(String(150), nullable=False)
    description = Column(Text)
    address = Column(String(255))
    phone = Column(String(30))
    email = Column(String(150))
    status = Column(Enum("pending", "active", "suspended", name="business_status"), nullable=False, default="active")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="businesses")
    category = relationship("Category", back_populates="businesses")
    staff = relationship("Staff", back_populates="business", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="business", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="business")


class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    full_name = Column(String(150), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    business = relationship("Business", back_populates="staff")
    working_hours = relationship("WorkingHours", back_populates="staff", cascade="all, delete-orphan")
    exceptions = relationship("AvailabilityException", back_populates="staff", cascade="all, delete-orphan")
    services = relationship("Service", secondary="staff_services", back_populates="staff_members")
    appointments = relationship("Appointment", back_populates="staff")


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text)
    duration_minutes = Column(SmallInteger, nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    business = relationship("Business", back_populates="services")
    staff_members = relationship("Staff", secondary="staff_services", back_populates="services")
    appointments = relationship("Appointment", back_populates="service")


class StaffService(Base):
    __tablename__ = "staff_services"

    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="CASCADE"), primary_key=True)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), primary_key=True)


class WorkingHours(Base):
    __tablename__ = "working_hours"

    id = Column(Integer, primary_key=True)
    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(SmallInteger, nullable=False)  # 0 = Sunday ... 6 = Saturday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    staff = relationship("Staff", back_populates="working_hours")


class AvailabilityException(Base):
    __tablename__ = "availability_exceptions"
    __table_args__ = (UniqueConstraint("staff_id", "exception_date", name="uq_ae_staff_date"),)

    id = Column(Integer, primary_key=True)
    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    exception_date = Column(Date, nullable=False)
    is_closed = Column(Boolean, nullable=False, default=True)
    start_time = Column(Time)
    end_time = Column(Time)
    reason = Column(String(255))

    staff = relationship("Staff", back_populates="exceptions")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(
        Enum("pending", "confirmed", "cancelled", "completed", "no_show", name="appointment_status"),
        nullable=False,
        default="confirmed",
    )
    cancellation_reason = Column(String(255))
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    customer = relationship("User", back_populates="appointments")
    business = relationship("Business", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
    staff = relationship("Staff", back_populates="appointments")
    review = relationship("Review", back_populates="appointment", uselist=False, cascade="all, delete-orphan")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, unique=True)
    customer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    rating = Column(SmallInteger, nullable=False)
    comment = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())

    appointment = relationship("Appointment", back_populates="review")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"))
    type = Column(
        Enum("booking_confirmation", "reminder", "cancellation", "reschedule", "general", name="notification_type"),
        nullable=False,
    )
    message = Column(String(255), nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
