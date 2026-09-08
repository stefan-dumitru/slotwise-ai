"""
Live end-to-end smoke test for the Manager -> Worker -> Reviewer booking pipeline.

Exercises the real backend over HTTP: registers/logs in a dedicated test customer,
finds a real bookable service, sends a natural-language booking request through
/api/agent/chat, confirms the proposed appointment, verifies it was actually
created, then cancels it so repeated runs stay clean.

This calls the real OpenAI and Anthropic APIs and writes a real (then cancelled)
row to the database. It is a live integration check, not a mock/unit test.

Usage:
    python scripts/agent_smoke_test.py

Environment:
    SMOKE_TEST_BASE_URL  Backend base URL (default: http://127.0.0.1:8000)

Exit code 0 = pipeline healthy. Exit code 1 = something broke; see the printed
step that failed.
"""

import os
import sys
import time

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = os.environ.get("SMOKE_TEST_BASE_URL", "http://127.0.0.1:8000")
TEST_EMAIL = "smoke-test@internal.slotwise.dev"
TEST_PASSWORD = "smoke-test-password-123"
AGENT_TIMEOUT = 90  # the pipeline makes several real LLM calls


def step(label: str) -> None:
    print(f"\n-> {label}")


def fail(label: str, detail: str = "") -> None:
    print(f"\nFAIL: {label}")
    if detail:
        print(detail)
    sys.exit(1)


def main() -> None:
    start = time.time()

    step("Checking backend health")
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=5)
        r.raise_for_status()
    except Exception as exc:
        fail("Backend not reachable", str(exc))
    print("   backend is up")

    step("Authenticating the smoke-test customer account")
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"full_name": "Smoke Test", "email": TEST_EMAIL, "password": TEST_PASSWORD, "role": "customer"},
    )
    if r.status_code == 201:
        token = r.json()["access_token"]
    else:
        r = requests.post(f"{BASE_URL}/api/auth/login", data={"username": TEST_EMAIL, "password": TEST_PASSWORD})
        if r.status_code != 200:
            fail("Could not authenticate test account", r.text)
        token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   authenticated")

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

    step("Sending a natural-language booking request through the agent pipeline")
    message = f"I'd like to book {service['name']} at {business['name']} sometime this week."
    conversation = [{"role": "user", "content": message}]
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/api/agent/chat",
        json={"conversation": conversation},
        headers=headers,
        timeout=AGENT_TIMEOUT,
    )
    elapsed = time.time() - t0
    if r.status_code != 200:
        fail(f"Agent chat endpoint returned {r.status_code}", r.text)
    data = r.json()
    print(f"   agent responded in {elapsed:.1f}s with status={data['status']!r}")
    print(f"   reply: {data['reply']}")

    if data["status"] != "proposed":
        fail(
            f"Expected status 'proposed' but got {data['status']!r} — "
            "the Manager/Worker/Reviewer pipeline did not converge on a bookable slot",
            data["reply"],
        )
    proposal = data["proposal"]

    step("Confirming the proposed appointment")
    r = requests.post(
        f"{BASE_URL}/api/appointments",
        json={
            "service_id": proposal["service_id"],
            "staff_id": proposal["staff_id"],
            "start_time": proposal["start_time"],
        },
        headers=headers,
    )
    if r.status_code != 201:
        fail(f"Confirmation booking returned {r.status_code}", r.text)
    appointment = r.json()
    print(f"   appointment #{appointment['id']} created, status={appointment['status']!r}")

    step("Verifying the appointment actually exists")
    mine = requests.get(f"{BASE_URL}/api/appointments/me", headers=headers).json()
    if not any(a["id"] == appointment["id"] for a in mine):
        fail("Created appointment not found in /api/appointments/me")
    print("   confirmed present in the customer's appointment list")

    step("Cleaning up (cancelling the test appointment)")
    r = requests.post(f"{BASE_URL}/api/appointments/{appointment['id']}/cancel", headers=headers)
    if r.status_code != 200:
        print(f"   WARNING: cleanup failed ({r.status_code}) — appointment #{appointment['id']} left behind")
    else:
        print("   cleaned up")

    total = time.time() - start
    print(f"\nPASS — full pipeline verified in {total:.1f}s")
    sys.exit(0)


if __name__ == "__main__":
    main()
