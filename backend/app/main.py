from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import admin, agent, appointments, auth, businesses, notifications

app = FastAPI(title="SlotWise API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(businesses.router)
app.include_router(appointments.router)
app.include_router(agent.router)
app.include_router(admin.router)
app.include_router(notifications.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
