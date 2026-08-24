import json
from datetime import date

from functools import lru_cache

from openai import OpenAI
from sqlalchemy.orm import Session

from .. import crud
from ..config import settings


@lru_cache
def _get_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)

SYSTEM_PROMPT = """You are the Manager agent in a 3-agent appointment-booking assistant \
(Manager -> Worker -> Reviewer). You are the only agent who talks to the end user.

Your job: read the conversation and decide whether you have enough information to start \
looking for an appointment, or whether you need to ask the user a clarifying question first.

You need at minimum a rough idea of WHAT service the user wants (e.g. "haircut", "dentist \
checkup", "math tutoring"). You do NOT need an exact date/time before proceeding — if the \
user gave no date preference at all, that's fine, proceed anyway and the Worker will search \
a broad upcoming window.

Only ask a clarifying question if the request is too vague to search for at all (e.g. the \
user just says "book me something").

Today's date is {today}. If the user gives a relative date ("next Tuesday", "tomorrow", \
"this weekend"), resolve it to actual date(s) yourself and put them in date_from / date_to \
(YYYY-MM-DD). If no date was mentioned, leave date_from and date_to null.

Respond with ONLY a JSON object matching exactly one of these two shapes:

Shape A (need more info):
{{"action": "clarify", "message_to_user": "<question to ask the user>"}}

Shape B (ready to search):
{{"action": "proceed", "task_brief": {{
  "service_query": "<short search phrase for the service, e.g. 'haircut'>",
  "category_hint": "<category name if implied, else null>",
  "date_from": "<YYYY-MM-DD or null>",
  "date_to": "<YYYY-MM-DD or null>",
  "time_of_day_hint": "<morning|afternoon|evening or null>",
  "staff_preference": "<staff name if the user asked for someone specific, else null>",
  "notes": "<anything else relevant to the booking>"
}}}}

Known service categories on the platform: {categories}
"""


def build_task_brief(db: Session, conversation: list[dict], feedback: str | None = None) -> dict:
    categories = ", ".join(c.name for c in crud.get_categories(db)) or "none yet"
    system = SYSTEM_PROMPT.format(today=date.today().isoformat(), categories=categories)

    messages = [{"role": "system", "content": system}]
    messages.extend({"role": m["role"], "content": m["content"]} for m in conversation)
    if feedback:
        messages.append(
            {
                "role": "system",
                "content": f"A previous booking attempt was rejected by the Reviewer for this reason: "
                f"{feedback}. Take this into account.",
            }
        )

    response = _get_client().chat.completions.create(
        model=settings.manager_model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return json.loads(response.choices[0].message.content)
