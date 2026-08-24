from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .. import crud, models
from . import manager, reviewer, worker

MAX_REVIEW_RETRIES = 2


def handle_booking_request(db: Session, conversation: list[dict]) -> dict:
    manager_result = manager.build_task_brief(db, conversation)

    if manager_result.get("action") == "clarify":
        return {"status": "clarify", "reply": manager_result.get("message_to_user", "Could you tell me more?")}

    task_brief = manager_result.get("task_brief", {})
    feedback: str | None = None

    for _ in range(MAX_REVIEW_RETRIES + 1):
        worker_result = worker.run_worker(db, task_brief, conversation, feedback=feedback)

        if worker_result["type"] == "clarify":
            return {"status": "clarify", "reply": worker_result["question"]}

        try:
            service_id = int(worker_result["service_id"])
            staff_id = int(worker_result["staff_id"])
            start_time = datetime.fromisoformat(worker_result["start_time"])
        except (KeyError, ValueError, TypeError):
            feedback = "The proposal was malformed (missing or invalid service_id, staff_id, or start_time)."
            continue

        service = db.get(models.Service, service_id)
        staff = db.get(models.Staff, staff_id)
        if not service or not staff or staff.business_id != service.business_id:
            feedback = "The proposed service_id / staff_id do not refer to a valid, matching service and staff member."
            continue

        end_time = start_time + timedelta(minutes=service.duration_minutes)
        slot_free = crud.is_slot_free(db, staff_id, start_time, end_time)
        availability_check = {
            "slot_still_free": slot_free,
            "service_name": service.name,
            "business_name": staff.business.name,
            "staff_name": staff.full_name,
            "duration_minutes": service.duration_minutes,
            "price": float(service.price),
            "start_time": start_time.isoformat(),
        }

        review = reviewer.review_proposal(conversation, task_brief, worker_result, availability_check)

        if review.get("approved") and slot_free:
            return {
                "status": "proposed",
                "reply": review.get("confirmation_message") or "I found an option for you — want me to book it?",
                "proposal": {
                    "service_id": service_id,
                    "staff_id": staff_id,
                    "business_id": staff.business_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "service_name": service.name,
                    "business_name": staff.business.name,
                    "staff_name": staff.full_name,
                    "price": float(service.price),
                },
            }

        feedback = review.get("feedback") or "That slot was no longer available."

    return {
        "status": "failed",
        "reply": f"I wasn't able to lock in a booking after a few attempts. Last issue: {feedback} "
        "Could you try rephrasing your request?",
    }
