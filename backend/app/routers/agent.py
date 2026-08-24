from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..agents.orchestrator import handle_booking_request
from ..auth_utils import get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=schemas.AgentChatResponse)
def chat(
    payload: schemas.AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    conversation = [m.model_dump() for m in payload.conversation]

    result = handle_booking_request(db, conversation)

    updated_conversation = conversation + [{"role": "assistant", "content": result["reply"]}]

    return schemas.AgentChatResponse(
        reply=result["reply"],
        status=result["status"],
        proposal=result.get("proposal"),
        conversation=updated_conversation,
    )
