"""
Live health check for the deployed Railway stack (backend + frontend).

Hits the real, publicly deployed URLs directly -- no Docker, no local
servers, no test doubles. Verifies the backend is actually serving traffic
(not crash-looping), that it can reach its database, that the database
schema actually matches what the deployed code expects (a round trip
through an endpoint that touches every column on a model, not just one
that happens to still work), that CORS is configured for the real
frontend origin, and that the frontend is serving the real app with its
API_BASE correctly wired to the backend.

This exists because a Railway deploy can "succeed" (container starts,
Railway shows a green checkmark) while being completely broken in ways
that are invisible until a real browser hits it -- a stray dashboard
Custom Start Command silently overriding the Dockerfile's CMD, a CORS
origin that doesn't match production, or a database that was never
migrated for a schema change the code now expects. All three of these
have actually happened to this project.

Usage:
    python scripts/railway_deploy_check.py

Environment:
    RAILWAY_BACKEND_URL   Backend base URL  (default: https://backend-production-873e7.up.railway.app)
    RAILWAY_FRONTEND_URL  Frontend base URL (default: https://slotwise.up.railway.app)

Exit code 0 = the deployed stack is actually healthy end-to-end. Exit code
1 = something is broken; see the printed step that failed.
"""

import json
import os
import sys
import urllib.error
import urllib.request

BACKEND_URL = os.environ.get("RAILWAY_BACKEND_URL", "https://backend-production-873e7.up.railway.app").rstrip("/")
FRONTEND_URL = os.environ.get("RAILWAY_FRONTEND_URL", "https://slotwise.up.railway.app").rstrip("/")
TIMEOUT = 15


class CheckFailed(Exception):
    pass


def step(label: str) -> None:
    print(f"\n-> {label}")


def http_request(url: str, method: str = "GET", headers: dict | None = None):
    request = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
            return resp.status, resp.headers, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read().decode("utf-8", errors="replace")


def check_json_ok(label: str, url: str, validator) -> None:
    step(f"{label} ({url})")
    status, _, body = http_request(url)
    if status != 200:
        raise CheckFailed(f"{label} returned HTTP {status}: {body[:300]}")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise CheckFailed(f"{label} did not return valid JSON: {body[:300]}")
    if not validator(data):
        raise CheckFailed(f"{label} returned unexpected data: {body[:300]}")
    print("   ok")


def main() -> None:
    check_json_ok(
        "Backend health endpoint",
        f"{BACKEND_URL}/api/health",
        lambda data: data.get("status") == "ok",
    )

    check_json_ok(
        "Backend database connectivity (categories endpoint)",
        f"{BACKEND_URL}/api/categories",
        lambda data: isinstance(data, list),
    )

    check_json_ok(
        "Backend businesses endpoint (full schema round trip)",
        f"{BACKEND_URL}/api/businesses",
        lambda data: isinstance(data, list),
    )

    step(f"CORS preflight for the real frontend origin ({FRONTEND_URL})")
    status, headers, _ = http_request(
        f"{BACKEND_URL}/api/auth/login",
        method="OPTIONS",
        headers={
            "Origin": FRONTEND_URL,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    allow_origin = headers.get("Access-Control-Allow-Origin") if headers else None
    if allow_origin != FRONTEND_URL:
        raise CheckFailed(
            f"CORS preflight did not allow {FRONTEND_URL} "
            f"(got Access-Control-Allow-Origin={allow_origin!r}, HTTP {status})"
        )
    print(f"   backend allows requests from {FRONTEND_URL}")

    step(f"Frontend is serving the real app ({FRONTEND_URL}/)")
    status, _, body = http_request(f"{FRONTEND_URL}/")
    if status != 200 or "<title>SlotWise</title>" not in body:
        raise CheckFailed(f"frontend did not return the expected app HTML (HTTP {status}): {body[:300]}")
    print("   ok")

    step("Frontend's API_BASE is wired to the backend")
    status, _, body = http_request(f"{FRONTEND_URL}/.env")
    if status != 200 or BACKEND_URL not in body:
        raise CheckFailed(f"frontend .env missing or pointing at the wrong backend: {body!r}")
    print(f"   .env contains API_BASE pointing at {BACKEND_URL}")

    print("\nPASS — Railway deployment (backend + frontend) is healthy end-to-end")
    print(f"   Backend:  {BACKEND_URL}")
    print(f"   Frontend: {FRONTEND_URL}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    try:
        main()
    except CheckFailed as exc:
        print(f"\nFAIL: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\nFAIL (unexpected error): {exc}")
        sys.exit(1)
