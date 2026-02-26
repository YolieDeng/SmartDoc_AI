from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.services.qa_service import ask, ask_stream

router = APIRouter()


class AskRequest(BaseModel):
    question: str
    session_id: str | None = None


@router.post("/ask")
async def ask_question(req: AskRequest):
    result = await ask(req.question, session_id=req.session_id)
    return result


@router.post("/ask/stream")
async def ask_question_stream(req: AskRequest):
    return EventSourceResponse(
        ask_stream(req.question, session_id=req.session_id)
    )
