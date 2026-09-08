---
name: agent-pipeline-check
description: Run a live end-to-end smoke test of the Manager/Worker/Reviewer AI booking pipeline against the running backend — sends a real natural-language booking request, confirms the proposed appointment, verifies it landed in the database, and cleans up after itself.
---

# Agent Pipeline Check

Use this skill when the user asks to verify, test, smoke-test, or sanity-check the AI booking pipeline (the Manager -> Worker -> Reviewer agents), or before deploying changes that touch `backend/app/agents/` or the `/api/agent/chat` endpoint.

This exercises the real OpenAI and Anthropic APIs and writes a real (then cancelled) row to the database — it is a live integration check, not a mock/unit test. Treat a failure as a real signal, not noise.

## Prerequisites

- `backend/.env` must have real `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and working MySQL credentials.
- The database needs at least one active business with a service and configured working hours (the seeded demo data satisfies this).

## Steps

1. Check whether the backend is already running:

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/health -UseBasicParsing -TimeoutSec 3
```

2. If it's not reachable, start it in the background from `backend/`:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Wait a couple of seconds and re-check health before continuing. If you had to start it, leave it running afterward — starting the backend is a side effect of running this check, not something to clean up.

3. Run the smoke test script from `backend/`:

```powershell
.venv\Scripts\python.exe scripts\agent_smoke_test.py
```

To check a deployed environment instead of localhost, set `SMOKE_TEST_BASE_URL` first:

```powershell
$env:SMOKE_TEST_BASE_URL = "https://backend-production-873e7.up.railway.app"
.venv\Scripts\python.exe scripts\agent_smoke_test.py
```

4. Report the result to the user:
   - If it exits 0: summarize each step it passed (booking request sent, agent proposed a real slot, booking confirmed, appointment verified, cleanup succeeded) and the total time taken.
   - If it exits non-zero: show the exact step that failed and the error/response body the script printed — point at the specific stage (agent response vs. confirmation vs. verification vs. cleanup) so the user knows where to look, don't just say "it failed."

Do not modify the script's assertions to force a pass. A failure here means something in the pipeline actually broke.
