from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.auth_utils import hash_password
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    """A fresh in-memory SQLite database per test, so tests never share state."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """A FastAPI TestClient wired to the isolated db_session instead of MySQL."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seed_business(db_session):
    """An owner, an active business, its default staff member, one service,
    and working hours on every day of the week (avoids weekday-dependent
    flakiness in tests that book relative to "today")."""
    owner = models.User(
        full_name="Test Owner",
        email="owner@slotwise-tests.dev",
        password_hash=hash_password("password123"),
        role="business_owner",
    )
    db_session.add(owner)
    db_session.flush()

    business = models.Business(owner_id=owner.id, name="Test Business", status="active")
    db_session.add(business)
    db_session.flush()

    staff = models.Staff(business_id=business.id, user_id=owner.id, full_name=owner.full_name)
    db_session.add(staff)
    db_session.flush()

    service = models.Service(
        business_id=business.id, name="Test Service", duration_minutes=30, price=25.0, is_active=True
    )
    db_session.add(service)
    db_session.flush()

    for day_of_week in range(7):
        db_session.add(
            models.WorkingHours(staff_id=staff.id, day_of_week=day_of_week, start_time=time(9, 0), end_time=time(17, 0))
        )
    db_session.commit()

    return {"owner": owner, "business": business, "staff": staff, "service": service}


def register(client, email, password="password123", role="customer", full_name="Test User"):
    resp = client.post(
        "/api/auth/register",
        json={"full_name": full_name, "email": email, "password": password, "role": role},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
