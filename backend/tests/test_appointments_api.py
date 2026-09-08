from datetime import date, timedelta

from conftest import auth_headers, register


def test_register_and_login(client):
    token = register(client, "alice@slotwise-tests.dev")
    assert token

    resp = client.post("/api/auth/login", data={"username": "alice@slotwise-tests.dev", "password": "password123"})
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "alice@slotwise-tests.dev"


def test_duplicate_email_registration_rejected(client):
    register(client, "bob@slotwise-tests.dev")
    resp = client.post(
        "/api/auth/register",
        json={"full_name": "Bob Again", "email": "bob@slotwise-tests.dev", "password": "password123", "role": "customer"},
    )
    assert resp.status_code == 400


def test_unauthenticated_request_rejected(client):
    resp = client.get("/api/appointments/me")
    assert resp.status_code == 401


def _set_up_bookable_business(client, owner_email="owner1@slotwise-tests.dev"):
    owner_token = register(client, owner_email, role="business_owner")
    business = client.post("/api/businesses", json={"name": "Salon X"}, headers=auth_headers(owner_token)).json()
    service = client.post(
        f"/api/businesses/{business['id']}/services",
        json={"name": "Haircut", "duration_minutes": 30, "price": 25.0},
        headers=auth_headers(owner_token),
    ).json()
    staff_id = client.get(f"/api/businesses/{business['id']}/staff").json()[0]["id"]
    for day_of_week in range(7):
        client.post(
            f"/api/staff/{staff_id}/working-hours",
            json={"day_of_week": day_of_week, "start_time": "09:00:00", "end_time": "17:00:00"},
            headers=auth_headers(owner_token),
        )
    return owner_token, business, service, staff_id


def test_full_booking_lifecycle(client):
    _, business, service, staff_id = _set_up_bookable_business(client)
    customer_token = register(client, "customer1@slotwise-tests.dev")

    start_time = f"{(date.today() + timedelta(days=3)).isoformat()}T10:00:00"
    booking = client.post(
        "/api/appointments",
        json={"service_id": service["id"], "staff_id": staff_id, "start_time": start_time},
        headers=auth_headers(customer_token),
    )
    assert booking.status_code == 201
    appt = booking.json()
    assert appt["status"] == "confirmed"

    conflict = client.post(
        "/api/appointments",
        json={"service_id": service["id"], "staff_id": staff_id, "start_time": start_time},
        headers=auth_headers(customer_token),
    )
    assert conflict.status_code == 409

    mine = client.get("/api/appointments/me", headers=auth_headers(customer_token)).json()
    assert any(a["id"] == appt["id"] for a in mine)

    cancel = client.post(f"/api/appointments/{appt['id']}/cancel", headers=auth_headers(customer_token))
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"


def test_cannot_review_an_appointment_that_is_not_completed(client):
    _, business, service, staff_id = _set_up_bookable_business(client, owner_email="owner2@slotwise-tests.dev")
    customer_token = register(client, "customer2@slotwise-tests.dev")

    start_time = f"{(date.today() + timedelta(days=2)).isoformat()}T09:00:00"
    appt = client.post(
        "/api/appointments",
        json={"service_id": service["id"], "staff_id": staff_id, "start_time": start_time},
        headers=auth_headers(customer_token),
    ).json()

    resp = client.post(f"/api/appointments/{appt['id']}/review", json={"rating": 5}, headers=auth_headers(customer_token))
    assert resp.status_code == 400
