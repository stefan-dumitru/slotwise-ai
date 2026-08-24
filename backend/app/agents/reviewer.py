import json
from functools import lru_cache

from openai import OpenAI

from ..config import settings


@lru_cache
def _get_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)

SYSTEM_PROMPT = """You are the Reviewer agent in a 3-agent appointment booking assistant \
(Manager -> Worker -> Reviewer). The Worker has proposed one specific appointment. You are \
given the original conversation, the task brief, the Worker's proposal, and the result of a \
deterministic database re-check of that exact slot.

Approve the proposal only if ALL of these hold:
- availability_check.slot_still_free is true
- the proposed service genuinely matches what the user asked for
- the proposed time reasonably matches any date/time preference the user expressed (if the \
  user gave no preference, any future time is fine)

If you reject, write a short, specific feedback string explaining what's wrong so the Worker \
can try again (e.g. "the user asked for a dentist, not a hygienist" or "slot is no longer free").

If you approve, write a warm, concise confirmation_message that presents this as a proposal \
awaiting the user's confirmation, NOT as something already booked — state the service, \
business, staff member, and date/time in plain language, and end by asking the user to confirm \
(e.g. "I found a Women's Haircut with Sofia at The Gilded Chair on Friday at 2:00 PM — want me \
to book it?"). The actual booking will only be created after the user explicitly confirms.

Respond with ONLY this JSON shape:
{"approved": true|false, "feedback": "<string, empty if approved>", "confirmation_message": "<string, empty if rejected>"}
"""


def review_proposal(conversation: list[dict], task_brief: dict, proposal: dict, availability_check: dict) -> dict:
    conversation_text = "\n".join(f"{m['role']}: {m['content']}" for m in conversation)
    user_content = (
        f"Conversation so far:\n{conversation_text}\n\n"
        f"Task brief:\n{json.dumps(task_brief)}\n\n"
        f"Worker's proposal:\n{json.dumps(proposal)}\n\n"
        f"Deterministic availability re-check:\n{json.dumps(availability_check)}"
    )

    response = _get_client().chat.completions.create(
        model=settings.reviewer_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return json.loads(response.choices[0].message.content)
