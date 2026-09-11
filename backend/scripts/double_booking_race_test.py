"""
Concurrency stress test for the booking system's conflict prevention.

Fires a burst of genuinely simultaneous booking requests -- from N different
real customer accounts, over N real OS threads released at the same instant
via a threading.Barrier -- all targeting the exact same staff member and
time slot on a real running backend. Then asserts the database ended up
with exactly one confirmed appointment for that slot, not more.

This exists because `crud.create_appointment` uses a check-then-insert
pattern (see the comment above `is_slot_free` in crud.py) with no row
locking. Under real concurrent load, two requests can both pass the
"is this slot free?" check before either commits, both insert, and the
business ends up double-booked. A sequential test suite (pytest) cannot
catch this class of bug no matter how many cases it covers -- it only
shows up under actual concurrency. This is a live integration check
against a real backend and a real database, not a mock.

Every appointment this script creates -- including any extra ones from a
detected double-booking -- is cancelled during cleanup, regardless of
whether the check passes or fails.

Usage:
    python scripts/double_booking_race_test.py

Environment:
    RACE_TEST_BASE_URL    Backend base URL (default: http://127.0.0.1:8000)
    RACE_TEST_CONCURRENCY Number of simultaneous booking attempts (default: 8)

Exit code 0 = exactly one booking won the race and every other attempt was
correctly rejected as a conflict. Exit code 1 = something broke, including
-- most importantly -- an actual double-booking being detected.
"""

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = os.environ.get("RACE_TEST_BASE_URL", "http://127.0.0.1:8000")
CONCURRENCY = int(os.environ.get("RACE_TEST_CONCURRENCY", "8"))
PASSWORD = "race-test-password-123"


def step(label: str) -> None:
    print(f"\n-> {label}")


def fail(label: str, detail: str = "") -> None:
    print(f"\nFAIL: {label}")
    if detail:
        print(detail)
    sys.exit(1)


def get_customer_token(index: int) -> str:
    email = f"race-test-{index}@internal.slotwise.dev"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"full_name": f"Race Test {index}", "email": email, "password": PASSWORD, "role": "customer"},
    )
    if r.status_code == 201:
        return r.json()["access_token"]
    r = requests.post(f"{BASE_URL}/api/auth/login", data={"username": email, "password": PASSWORD})
    if r.status_code != 200:
        fail(f"Could not authenticate race-test customer #{index}", r.text)
    return r.json()["access_token"]


def book(barrier: threading.Barrier, token: str, service_id: int, staff_id: int, start_time: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    barrier.wait()  # every thread blocks here until all CONCURRENCY threads are ready, then all release together
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/api/appointments",
        json={"service_id": service_id, "staff_id": staff_id, "start_time": start_time},
        headers=headers,
    )
    return {"status": r.status_code, "body": r.text, "elapsed": time.time() - t0, "token": token}


def main() -> None:
    start = time.time()

    step("Checking backend health")
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=5)
        r.raise_for_status()
    except Exception as exc:
        fail("Backend not reachable", str(exc))
    print("   backend is up")

    step("Finding a real bookable business + service")
    businesses = requests.get(f"{BASE_URL}/api/businesses").json()
    target = None
    for business in businesses:
        services = requests.get(f"{BASE_URL}/api/businesses/{business['id']}/services").json()
        if services:
            target = (business, services[0])
            break
    if not target:
        fail("No active business with at least one service found — seed data first.")
    business, service = target
    print(f"   using '{service['name']}' at '{business['name']}'")

    step("Finding a real open slot to attack")
    slot = None
    for days_ahead in range(1, 15):
        slot_date = date.today() + timedelta(days=days_ahead)
        r = requests.get(
            f"{BASE_URL}/api/businesses/{business['id']}/services/{service['id']}/slots",
            params={"slot_date": slot_date.isoformat()},
        )
        r.raise_for_status()
        slots = r.json()
        if slots:
            slot = slots[0]
            break
    if not slot:
        fail("No open slots found in the next 14 days — seed data or working hours may be missing.")
    print(f"   targeting staff #{slot['staff_id']} ({slot['staff_name']}) at {slot['start_time']}")

    step(f"Authenticating {CONCURRENCY} separate customer accounts")
    tokens = [get_customer_token(i) for i in range(CONCURRENCY)]
    print(f"   {len(tokens)} accounts ready")

    step(f"Firing {CONCURRENCY} simultaneous booking requests at the same slot")
    barrier = threading.Barrier(CONCURRENCY)
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [
            pool.submit(book, barrier, token, service["id"], slot["staff_id"], slot["start_time"])
            for token in tokens
        ]
        results = [f.result() for f in futures]

    successes = [r for r in results if r["status"] == 201]
    conflicts = [r for r in results if r["status"] == 409]
    others = [r for r in results if r["status"] not in (201, 409)]

    print(f"   {len(successes)} succeeded, {len(conflicts)} correctly rejected as conflicts, {len(others)} unexpected")

    step("Cleaning up every appointment this run created")
    created_ids = []
    for r in successes:
        appointment_id = json.loads(r["body"])["id"]
        created_ids.append(appointment_id)
        cancel = requests.post(
            f"{BASE_URL}/api/appointments/{appointment_id}/cancel",
            headers={"Authorization": f"Bearer {r['token']}"},
        )
        if cancel.status_code != 200:
            print(f"   WARNING: cleanup failed for appointment #{appointment_id} ({cancel.status_code})")
    print(f"   cancelled {len(created_ids)} appointment(s): {created_ids}")

    if others:
        fail(
            f"{len(others)} request(s) returned neither 201 nor 409 — something other than the conflict "
            "check is broken",
            "\n".join(f"HTTP {r['status']}: {r['body'][:200]}" for r in others),
        )

    if len(successes) == 0:
        fail(
            "Every single request was rejected, including the first — the slot may not have actually "
            "been free, or booking is broken outright.",
            "\n".join(f"HTTP {r['status']}: {r['body'][:200]}" for r in results),
        )

    if len(successes) > 1:
        fail(
            f"DOUBLE-BOOKING DETECTED — {len(successes)} concurrent requests all succeeded for the same "
            f"slot (appointment ids: {created_ids}). The check-then-insert race in crud.create_appointment "
            "let more than one booking through.",
        )

    total = time.time() - start
    print(f"\nPASS — {CONCURRENCY} concurrent requests raced for one slot, exactly 1 won, {len(conflicts)} correctly rejected ({total:.1f}s)")


if __name__ == "__main__":
    main()
