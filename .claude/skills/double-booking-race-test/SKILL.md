---
name: double-booking-race-test
description: Fire N genuinely simultaneous booking requests from separate real customer accounts at the exact same staff member and time slot on a running backend, and assert exactly one wins — a live concurrency test for the booking system's conflict prevention that a sequential test suite cannot perform.
---

# Double-Booking Race Test

Use this skill when the user asks to check for double-booking, race conditions, or concurrency bugs in the booking flow, or after changing `crud.create_appointment` / `crud.is_slot_free` in `backend/app/crud.py`.

This is a live integration check against a real running backend and a real database — not a mock, and not the pytest suite. It exists because `crud.create_appointment` uses a check-then-insert pattern (see the comment above `is_slot_free` in `backend/app/crud.py`) with no row locking: two requests can both pass the "is this slot free?" check before either commits, and both succeed. A sequential test — pytest included — cannot reproduce this no matter how many cases it covers; it only shows up under actual concurrent load, which is exactly what this script creates.

## Prerequisites

- A running backend, reachable at `RACE_TEST_BASE_URL` (default `http://127.0.0.1:8000`). If nothing is running there, start the local dev backend the same way `agent-pipeline-check` does, from `backend/`:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Leave it running afterward if you had to start it — that's a side effect of running the check, not something to clean up.

- The database needs at least one active business with a service, staff, and configured working hours (seeded demo data satisfies this).

## Steps

1. Run the script from `backend/`:

```powershell
.venv\Scripts\python.exe scripts\double_booking_race_test.py
```

It authenticates several dedicated `race-test-N@internal.slotwise.dev` customer accounts, finds a real open slot for a real service, then releases all of them at the same instant against `POST /api/appointments` using a `threading.Barrier` (not just "started around the same time" — genuinely synchronized). It always cancels every appointment it created during cleanup, regardless of outcome, so repeated runs stay clean.

To point it at a different backend (Docker, Railway) or change how many requests race:

```powershell
$env:RACE_TEST_BASE_URL = "http://localhost:8001"
$env:RACE_TEST_CONCURRENCY = "16"
.venv\Scripts\python.exe scripts\double_booking_race_test.py
```

2. Report the result:
   - If it exits 0: exactly one request won the race and every other one was correctly rejected with HTTP 409 — report the concurrency level used and the total time.
   - If it exits non-zero because **more than one request succeeded**: this is a real double-booking — report it as a genuine bug, not a flaky test. Show the appointment IDs and how many succeeded out of how many. Do not weaken the assertion or dismiss it as a test artifact; fixing it means adding real locking (e.g. `SELECT ... FOR UPDATE` on the staff's appointments for that time window, or a unique constraint) inside `crud.create_appointment`, not retrying the test.
   - If it exits non-zero because **zero requests succeeded**: the slot search likely picked a slot that wasn't actually free, or booking is broken outright — check the printed response bodies.
   - If it exits non-zero for any other reason (an unexpected non-409 status): something besides the conflict check itself is broken — show the exact response.

This check creates and then cancels real rows in whatever database the target backend is using — never point `RACE_TEST_BASE_URL` at a production environment without the user's explicit go-ahead first, since concurrent writes against a live production database are a bigger deal than against local/Docker dev data.
