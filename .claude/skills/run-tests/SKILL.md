---
name: run-tests
description: Run the backend's pytest suite (unit tests for the scheduling engine, integration tests for the API via FastAPI's TestClient against an isolated in-memory SQLite database, and authorization/permission tests) with a coverage report.
---

# Run Tests

Use this skill when the user asks to run the tests, check test coverage, or verify nothing broke after a backend code change — especially changes to `backend/app/crud.py`, `backend/app/routers/`, or `backend/app/auth_utils.py`.

This is a fast, self-contained test suite: every test runs against an in-memory SQLite database created fresh per test (see `backend/tests/conftest.py`), so it needs no running MySQL server, no Docker, and no API keys. It should typically finish in well under 30 seconds.

## Steps

1. Run from `backend/`:

```powershell
.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing
```

2. Report the result:
   - If all tests pass: state the pass count and the overall coverage percentage from the report.
   - If any test fails: show the failing test name(s) and the assertion/traceback pytest printed — don't summarize it away, the exact failure line is what tells the user what broke.
   - Low coverage in `app/agents/` (Manager/Worker/Reviewer/orchestrator) is expected and not a problem — those modules call real OpenAI/Anthropic APIs and are intentionally covered by the separate `agent-pipeline-check` skill (a live integration check) instead of being mocked here.

3. If the user changed something in `app/crud.py`, `app/routers/`, `app/models.py`, or `app/schemas.py` and no test covers it, mention that as a gap — don't silently let coverage regress without at least flagging it.

Do not weaken or delete an assertion just to make a test pass. A failing test here means the change broke real, previously-verified behavior (booking conflicts, cross-owner authorization, review timing rules, etc.) — fix the code or intentionally update the test to reflect a real, deliberate behavior change, never the other way around by default.
