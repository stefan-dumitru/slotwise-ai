---
name: docker-stack-check
description: Build and boot the full Docker Compose stack (MySQL + FastAPI backend + nginx-served frontend), verify every service actually works (health, real database round trip, correct frontend config). Leaves the stack running if it passes, tears it down only if it fails.
---

# Docker Stack Check

Use this skill when the user asks to verify the project's Docker/containerization setup, check that the app boots in Docker, or after changing `docker-compose.yml`, `backend/Dockerfile`, or `frontend/Dockerfile`.

This builds real images and starts real containers (MySQL, backend, frontend) — it is a live integration check of the containerized stack, not a syntax lint. Docker Desktop (or an equivalent daemon) must be running first.

## Prerequisites

- Docker daemon running — check with `docker info`. If it's not running, ask the user to start Docker Desktop before proceeding; don't try to start it yourself.
- `backend/.env` must exist with real `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. — the backend container loads it via `env_file` in `docker-compose.yml`. The MySQL connection settings in it don't matter for this check (compose overrides them to point at the containerized `mysql` service instead).

## Steps

1. Confirm the daemon is reachable:

```powershell
docker info --format "{{.ServerVersion}}"
```

If this errors, stop and tell the user to start Docker Desktop.

2. Run the check script from the project root:

```powershell
python scripts\docker_stack_check.py
```

It first tears down any leftover containers from a previous run (`docker compose down --remove-orphans`) so it always starts from a clean slate — there's no need to manually delete containers before running this. Then it builds all three images, starts the stack, polls the backend's health endpoint, polls a real database-backed endpoint (`/api/categories`) to confirm the backend can actually reach MySQL through the container network (not just that the process is alive), polls the frontend, and verifies the frontend's `.env` was generated correctly inside the nginx container.

**Teardown behavior**: if the check passes, the stack is left running (that's the default now — the point of the check is to prove it works, and a working stack is more useful running than torn down). If it fails, the stack is torn down automatically so a half-started, broken stack doesn't linger and confuse the next run. To force teardown even on a pass (e.g. for a strict CI-style run with zero side effects), set `TEARDOWN_MODE=always` before invoking:

```powershell
$env:TEARDOWN_MODE = "always"
python scripts\docker_stack_check.py
```

3. Report the result:
   - If it exits 0: summarize each service verified (MySQL healthy, backend up with real DB connectivity, frontend serving, frontend config correctly wired to the backend), total time, and remind the user the stack is now running at `http://localhost:8080` (frontend) / `http://localhost:8001` (backend) unless they set `TEARDOWN_MODE=always`.
   - If it exits non-zero: identify exactly which stage failed (image build, container startup, a specific service never becoming healthy, or the frontend config check) and show the relevant output the script printed. A build failure usually means a Dockerfile/dependency problem; a service-never-healthy failure usually means a runtime/config problem (e.g. `backend/.env` missing a required value). The stack is already torn down in this case — no manual cleanup needed.

The `mysql_data` volume persists across every run regardless of teardown mode (schema is only initialized on first boot against an empty volume) — deleting and recreating containers never loses seeded data, only `docker compose down -v` (never used by this script) would.
