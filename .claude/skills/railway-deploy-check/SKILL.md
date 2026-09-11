---
name: railway-deploy-check
description: Hit the real, deployed Railway URLs (backend + frontend) directly and verify the production stack is actually healthy — backend reachable, real database round trip through a schema-sensitive endpoint, CORS configured for the real frontend origin, and frontend correctly wired to the backend.
---

# Railway Deploy Check

Use this skill when the user asks to verify the production/Railway deployment is healthy, after a Railway redeploy, after changing `CORS_ORIGINS` or any other Railway environment variable, or after a database migration that was applied directly against the Railway MySQL database.

This is a live check against the real public URLs — no Docker, no local servers, no mocks. It exists because a Railway deploy can show a green checkmark while still being broken in ways invisible until a real browser hits it: a stray dashboard Custom Start Command silently overriding the Dockerfile's `CMD`, a `CORS_ORIGINS` value that doesn't match the actual frontend origin, or a database that was never migrated for a schema change the deployed code now expects. All three of these have actually happened on this project.

## Prerequisites

None — this only makes outbound HTTPS requests to the already-deployed URLs. No Docker daemon, no local `.env`, no credentials needed.

## Steps

1. Run the check script from the project root:

```powershell
python scripts\railway_deploy_check.py
```

It checks, in order: the backend health endpoint, a database-backed endpoint (`/api/categories`) to confirm real DB connectivity, the `/api/businesses` endpoint specifically because it touches every column on the `Business` model — this is what catches a database that's reachable but out of sync with the deployed code's schema (exactly what happened when the map feature's `latitude`/`longitude` columns were added to the model but never migrated on Railway's database), a CORS preflight against the real frontend origin to confirm `Access-Control-Allow-Origin` is actually present and correct, that the frontend is serving the real app HTML (not a Railway fallback/error page), and that the frontend's generated `.env` has `API_BASE` pointing at the right backend URL.

To check different URLs (e.g. after a domain change, or a staging environment), override before invoking:

```powershell
$env:RAILWAY_BACKEND_URL = "https://your-backend.up.railway.app"
$env:RAILWAY_FRONTEND_URL = "https://your-frontend.up.railway.app"
python scripts\railway_deploy_check.py
```

2. Report the result:
   - If it exits 0: summarize each check that passed (backend health, DB connectivity, schema round trip via businesses, CORS, frontend serving, frontend-to-backend wiring) and confirm the deployment is healthy end-to-end.
   - If it exits non-zero: identify exactly which check failed and show the error the script printed. A health-endpoint failure usually means the backend container is crash-looping (check its Deploy Logs on Railway — the `$PORT` / Custom Start Command bug is a known repeat offender here). A categories/businesses failure that's specifically HTTP 500 while health is fine usually means a database schema mismatch — a migration was applied to code but not to Railway's actual database. A CORS failure means `CORS_ORIGINS` on the backend service doesn't match the frontend's real origin exactly (no trailing slash, exact scheme/host). A frontend HTML or `.env` failure means the frontend's `API_BASE` variable is missing or wrong on Railway.

This check is read-only and side-effect-free — safe to run at any time, as often as needed.
