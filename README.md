# SlotWise

Appointment booking platform with an AI-assisted booking flow: describe what you need in
plain English and a Manager -> Worker -> Reviewer agent pipeline finds and books a real,
conflict-free slot for you.

- **Database**: MySQL — schema in [`database/schema.sql`](database/schema.sql)
- **Backend**: FastAPI (Python) — [`backend/`](backend/)
- **Frontend**: static HTML/JS — [`frontend/`](frontend/)
- **Agents**: Manager & Reviewer on OpenAI, Worker on Claude — [`backend/app/agents/`](backend/app/agents/)

## 1. Database

Already created if you ran `database/schema.sql` in MySQL Workbench. If not, run that script
against your MySQL server first.

## 2. Backend

A virtual environment with all dependencies already installed lives at `backend/.venv`.

```
cd backend
.venv\Scripts\activate
copy .env.example .env      # already done — just edit .env with your real values
```

Edit `backend/.env`:
- `MYSQL_*` — match your MySQL Workbench connection (host/port/user/password/database)
- `OPENAI_API_KEY` — used by the Manager and Reviewer agents
- `ANTHROPIC_API_KEY` — used by the Worker agent
- `TAVILY_API_KEY` — not used yet, safe to leave as-is

Then run the API:

```
uvicorn app.main:app --reload
```

It starts on `http://localhost:8000`. Interactive API docs: `http://localhost:8000/docs`.

## 3. Frontend

Plain static files, no build step. From `frontend/`, serve it with any static server, e.g.:

```
cd frontend
python -m http.server 5500
```

Then open `http://localhost:5500`. If you serve it from a different port, add that origin to
`CORS_ORIGINS` in `backend/.env` and restart the backend.

## 4. Try it

1. Register a **business_owner** account, then use the **"My Business"** tab to create a
   business, add a service (e.g. "Haircut", 30 min, $25), add staff, and set working hours.
2. Register a **customer** account (or log in as one).
3. Go to "Book with Assistant" and type something like *"I need a haircut sometime next
   week"*. The Manager will interpret it, the Worker will search real services/slots, the
   Reviewer will double-check the proposal, and — once approved — the backend commits the
   appointment.
4. For platform administration (categories, business status, user roles), you need an
   **admin** account. Registration deliberately can't create one (`role` is limited to
   `customer`/`business_owner`), so the first admin has to be bootstrapped directly against
   the database — e.g. from `backend/`, with the venv active:
   ```python
   from app.database import SessionLocal
   from app import models
   from app.auth_utils import hash_password
   db = SessionLocal()
   db.add(models.User(full_name="Admin", email="admin@example.com",
                       password_hash=hash_password("your-password"), role="admin"))
   db.commit()
   ```
   After that, admins can promote other users via the **"Admin"** tab (or
   `PATCH /api/admin/users/{id}/role`).

## Notes / known limitations (by design, for a first pass)

- Booking race conditions are handled with a check-then-insert pattern, not row locking —
  fine for demo/dev load, would need `SELECT ... FOR UPDATE` (or a serializable transaction)
  under real concurrent traffic.
- Notifications are in-app only (bell icon, top right) — no email/SMS delivery.
- Suspending a business (via the Admin tab) hides it from Browse/the agent's search, but the
  direct `POST /api/appointments` endpoint doesn't itself check business/service status —
  edge case, not a path the UI exposes.
