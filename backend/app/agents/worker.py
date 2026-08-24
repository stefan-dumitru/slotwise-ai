import json
from datetime import date, timedelta
from functools import lru_cache

import anthropic
from sqlalchemy.orm import Session

from .. import crud, models
from ..config import settings

MAX_TOOL_ITERATIONS = 6


@lru_cache
def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are the Worker agent in a 3-agent appointment booking assistant \
(Manager -> Worker -> Reviewer). The Manager has already produced a task brief describing \
what the user wants. Your job is to use the provided tools against the real database to \
find a bookable option and end your turn with exactly one of:

- propose_appointment: one specific, verified service + staff member + start time
- ask_clarification: a question for the user, if you get stuck

Rules:
- Always call search_services first to find the actual service_id(s) that match the brief.
  Never guess an id.
- Then call list_available_slots for the matching service to find a real, open slot.
- Prefer a slot matching any date/time-of-day preference in the brief; if nothing matches
  exactly, propose the closest available option and say so in your summary.
- list_available_slots returns only the first `limit` slots (default 40) in chronological
  order. If none of them match a stated time-of-day preference (e.g. all returned slots are
  morning but the user wants afternoon), don't conclude afternoons are unavailable — call it
  again with a higher limit before giving up.
- If search_services finds nothing relevant, or no matching slots exist even after raising
  the limit, call ask_clarification explaining the problem and asking how the user wants to
  proceed.
- Never call propose_appointment with values you have not verified via the tools.
- You must end every turn with exactly one call to propose_appointment or ask_clarification.
"""

TOOLS = [
    {
        "name": "search_services",
        "description": "Search the platform's services by free-text query and optional category name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "category": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_available_slots",
        "description": "List upcoming available appointment slots for a given service.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "integer"},
                "date_from": {"type": "string", "description": "YYYY-MM-DD, defaults to today"},
                "date_to": {"type": "string", "description": "YYYY-MM-DD, defaults to 14 days after date_from"},
                "staff_id": {"type": "integer", "description": "Restrict to one staff member, if requested"},
                "limit": {
                    "type": "integer",
                    "description": "Max slots to return (default 40). Raise this if you need to see further "
                    "into the day/week to satisfy a time-of-day or later-date preference.",
                },
            },
            "required": ["service_id"],
        },
    },
    {
        "name": "propose_appointment",
        "description": "Propose one specific, verified appointment to book. Ends your turn.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "integer"},
                "staff_id": {"type": "integer"},
                "start_time": {"type": "string", "description": "ISO 8601 datetime, e.g. 2026-08-25T14:00:00"},
                "summary": {"type": "string", "description": "One sentence describing this proposal for the user."},
            },
            "required": ["service_id", "staff_id", "start_time", "summary"],
        },
    },
    {
        "name": "ask_clarification",
        "description": "Ask the user a clarifying question because no suitable option could be found. Ends your turn.",
        "input_schema": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
    },
]


def _execute_search_services(db: Session, args: dict) -> list[dict]:
    services = crud.search_services(db, query=args.get("query"), category_name=args.get("category"))
    return [
        {
            "service_id": s.id,
            "business_id": s.business_id,
            "business_name": s.business.name,
            "service_name": s.name,
            "duration_minutes": s.duration_minutes,
            "price": float(s.price),
        }
        for s in services
    ]


def _execute_list_available_slots(db: Session, args: dict) -> list[dict] | dict:
    service = db.get(models.Service, args.get("service_id"))
    if not service:
        return {"error": "service_id not found"}

    date_from = date.fromisoformat(args["date_from"]) if args.get("date_from") else date.today()
    date_to = date.fromisoformat(args["date_to"]) if args.get("date_to") else date_from + timedelta(days=14)

    limit = min(int(args.get("limit") or 40), 150)
    slots = crud.compute_available_slots(db, service, date_from, date_to, staff_id=args.get("staff_id"), limit=limit)
    return [
        {
            "staff_id": s["staff_id"],
            "staff_name": s["staff_name"],
            "start_time": s["start_time"].isoformat(),
            "end_time": s["end_time"].isoformat(),
        }
        for s in slots
    ]


def run_worker(db: Session, task_brief: dict, conversation: list[dict], feedback: str | None = None) -> dict:
    conversation_text = "\n".join(f"{m['role']}: {m['content']}" for m in conversation)
    user_content = f"Task brief:\n{json.dumps(task_brief)}\n\nConversation so far:\n{conversation_text}"
    if feedback:
        user_content += f"\n\nYour previous proposal was rejected by the Reviewer: {feedback}\nTry again, taking this into account."

    messages = [{"role": "user", "content": user_content}]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = _get_client().messages.create(
            model=settings.worker_model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            break

        tool_results = []
        for block in tool_use_blocks:
            if block.name == "propose_appointment":
                return {"type": "propose", **block.input}
            if block.name == "ask_clarification":
                return {"type": "clarify", "question": block.input["question"]}
            if block.name == "search_services":
                result = _execute_search_services(db, block.input)
            elif block.name == "list_available_slots":
                result = _execute_list_available_slots(db, block.input)
            else:
                result = {"error": f"unknown tool {block.name}"}
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})

        messages.append({"role": "user", "content": tool_results})

    return {
        "type": "clarify",
        "question": "I couldn't quite pin down a bookable option. Could you tell me more specifically "
        "what service you're after and roughly when you'd like it?",
    }
