from fastapi import APIRouter, Depends
from app.core.config import get_settings
from app.core.security import current_user
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.models.entities import User
from app.schemas.chat import ChatIn, ChatOut
from app.services import llm
from app.services.chat_context import available_context, build_context

router = APIRouter(prefix='/chat', tags=['AI 问答'])


@router.get('/config')
def config(user: User = Depends(current_user)):
    settings = get_settings()
    return {'configured': llm.provider_ready(settings), 'model_label': settings.deepseek_model_label}


@router.post('', response_model=ChatOut)
async def chat(body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    context, summary = build_context(db, user, body.use_profile, body.use_saved_plans, body.plan_ids)
    result = await llm.complete(body.messages, context)
    return result.model_copy(update={'context': summary})


@router.get('/context')
def context(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return available_context(db, user)
