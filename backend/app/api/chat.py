from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, Session
from app.core.render import md
from app.schemas.chat import ChatAnswerBody, ChatAnswerResult, ChatMessageOut, ChatReply, ChatSendBody
from app.services import chat_agent

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/history", response_model=list[ChatMessageOut])
async def history(user: CurrentUser, session: Session):
    rows = await chat_agent.load_history(session, user.id, 60)
    return [
        ChatMessageOut(
            role=r.role,
            content=r.content,
            html=md(r.content) if r.role == "assistant" else "",
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.post("/messages", response_model=ChatReply)
async def send(body: ChatSendBody, user: CurrentUser, session: Session):
    return await chat_agent.send_message(session, user.id, body)


@router.post("/answer", response_model=ChatAnswerResult)
async def answer(body: ChatAnswerBody, user: CurrentUser, session: Session):
    return await chat_agent.answer_quiz(session, user.id, body.qid.strip(), body.answer)


@router.delete("/history", status_code=204)
async def clear(user: CurrentUser, session: Session):
    await chat_agent.clear_history(session, user.id)
    return Response(status_code=204)
