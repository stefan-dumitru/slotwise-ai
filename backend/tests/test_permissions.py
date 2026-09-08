from app import models
from app.auth_utils import create_access_token, hash_password
from conftest import auth_headers, register


def test_business_owner_cannot_manage_another_owners_business(client):
    owner_a_token = register(client, "ownerA@slotwise-tests.dev", role="business_owner")
    owner_b_token = register(client, "ownerB@slotwise-tests.dev", role="business_owner")

    business_a = client.post("/api/businesses", json={"name": "A's Shop"}, headers=auth_headers(owner_a_token)).json()

    resp = client.post(
        f"/api/businesses/{business_a['id']}/services",
        json={"name": "Sneaky Service", "duration_minutes": 30, "price": 10.0},
        headers=auth_headers(owner_b_token),
    )
    assert resp.status_code == 403


def test_customer_cannot_create_a_business(client):
    customer_token = register(client, "cust-perm@slotwise-tests.dev")
    resp = client.post("/api/businesses", json={"name": "Nope"}, headers=auth_headers(customer_token))
    assert resp.status_code == 403


def test_non_admin_cannot_access_admin_routes(client):
    owner_token = register(client, "owner-perm@slotwise-tests.dev", role="business_owner")
    resp = client.get("/api/admin/users", headers=auth_headers(owner_token))
    assert resp.status_code == 403


def test_admin_cannot_demote_themselves(client, db_session):
    admin = models.User(
        full_name="Admin", email="admin@slotwise-tests.dev", password_hash=hash_password("password123"), role="admin"
    )
    db_session.add(admin)
    db_session.commit()
    token = create_access_token(admin.id)

    resp = client.patch(f"/api/admin/users/{admin.id}/role", json={"role": "customer"}, headers=auth_headers(token))
    assert resp.status_code == 400
