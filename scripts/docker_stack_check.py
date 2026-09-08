"""
Cleans up any leftover containers from a previous run, then builds, starts,
and verifies the full Docker Compose stack (MySQL + backend + nginx
frontend) for this project. Always starts from a clean slate, so there's no
need to manually `docker compose down` before running this again.

Usage:
    python scripts/docker_stack_check.py

Requires Docker Desktop (or an equivalent Docker daemon) running, and
backend/.env populated with real values — the backend container loads it
via env_file in docker-compose.yml.

Exit code 0 = the stack builds, boots, and actually serves traffic (including
a real database round trip through the backend). Exit code 1 = something
broke; see the printed step that failed.

Teardown behavior (env var TEARDOWN_MODE):
    on-failure (default) - leave a passing stack running so it can be used;
                            tear down only if the check failed.
    always                - tear down regardless of outcome (strict CI-style).
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_URL = "http://localhost:8001"
FRONTEND_URL = "http://localhost:8080"
POLL_TIMEOUT = 120
POLL_INTERVAL = 3


class CheckFailed(Exception):
    pass


def step(label: str) -> None:
    print(f"\n-> {label}")


def run(cmd: list) -> subprocess.CompletedProcess:
    print(f"   $ {' '.join(cmd)}")
    return subprocess.run(
        cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def http_get(url: str, timeout: float = 5):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def wait_for(label: str, url: str, validator=None) -> None:
    step(f"Waiting for {label} ({url})")
    deadline = time.time() + POLL_TIMEOUT
    last_error = ""
    while time.time() < deadline:
        try:
            status, body = http_get(url)
            if status == 200 and (validator is None or validator(body)):
                print(f"   {label} is up")
                return
            last_error = f"HTTP {status}: {body[:200]}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(POLL_INTERVAL)
    raise CheckFailed(f"{label} never became healthy within {POLL_TIMEOUT}s — last error: {last_error}")


def main() -> None:
    start = time.time()

    step("Cleaning up any leftover containers from a previous run")
    run(["docker", "compose", "down", "--remove-orphans"])
    print("   clean slate")

    step("Building images")
    result = run(["docker", "compose", "build"])
    if result.returncode != 0:
        raise CheckFailed(f"docker compose build failed:\n{result.stdout}\n{result.stderr}")
    print("   images built")

    step("Starting the stack (mysql, backend, frontend)")
    result = run(["docker", "compose", "up", "-d"])
    if result.returncode != 0:
        raise CheckFailed(f"docker compose up failed:\n{result.stdout}\n{result.stderr}")
    print("   containers started")

    wait_for(
        "backend health endpoint",
        f"{BACKEND_URL}/api/health",
        lambda body: json.loads(body).get("status") == "ok",
    )
    wait_for(
        "backend database connectivity (categories endpoint)",
        f"{BACKEND_URL}/api/categories",
        lambda body: isinstance(json.loads(body), list),
    )
    wait_for("frontend (nginx)", f"{FRONTEND_URL}/")

    step("Verifying the frontend's .env was generated correctly inside the container")
    status, body = http_get(f"{FRONTEND_URL}/.env")
    if status != 200 or BACKEND_URL not in body:
        raise CheckFailed(f"frontend .env missing or wrong: {body!r}")
    print(f"   .env contains API_BASE pointing at {BACKEND_URL}")

    total = time.time() - start
    print(f"\nPASS — full stack (MySQL + backend + nginx frontend) built and verified in {total:.1f}s")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # "on-failure" (default): leave a passing stack running so it can actually be used;
    # tear down only when something broke, so a half-started stack doesn't linger.
    # "always": strict CI-style behavior, tear down regardless of outcome.
    teardown_mode = os.environ.get("TEARDOWN_MODE", "on-failure")

    exit_code = 0
    passed = False
    try:
        main()
        passed = True
    except CheckFailed as exc:
        print(f"\nFAIL: {exc}")
        exit_code = 1
    except Exception as exc:  # still tear down on any unexpected error
        print(f"\nFAIL (unexpected error): {exc}")
        exit_code = 1
    finally:
        if teardown_mode == "always" or not passed:
            print("\n-> Tearing down the stack")
            subprocess.run(["docker", "compose", "down"], cwd=PROJECT_ROOT)
        else:
            print("\n-> Leaving the stack running (pass, teardown mode = on-failure)")
            print(f"   Backend:  {BACKEND_URL}")
            print(f"   Frontend: {FRONTEND_URL}")
            print("   Run `docker compose down` when you're done, or set TEARDOWN_MODE=always to always clean up.")
    sys.exit(exit_code)
