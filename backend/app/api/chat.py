import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.core.config import get_settings
from app.core.security import current_user
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.models.entities import User
from app.schemas.chat import ChatIn, ChatOut
from app.services import llm
from app.services.chat_context import available_context, build_context

router = APIRouter(prefix='/chat', tags=['AI 问答'])


def _sse(event: str, payload: dict) -> str:
    return f'event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n'


@router.get('/config')
def config(user: User = Depends(current_user)):
    settings = get_settings()
    return {'configured': llm.provider_ready(settings), 'model_label': settings.deepseek_model_label}


@router.post('', response_model=ChatOut)
async def chat(body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    context, summary = build_context(db, user, body.use_profile, body.use_saved_plans, body.plan_ids)
    result = await llm.complete(body.messages, context)
    return result.model_copy(update={'context': summary})


@router.post('/stream')
async def chat_stream(body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """流式问答（SSE）：先发 meta（上下文摘要），再逐段发 delta，最后 done 或 error。

    与 ``POST /chat`` 同参数、同上下文与同审计边界；保留非流式接口用于兼容性测试。
    """
    context, summary = build_context(db, user, body.use_profile, body.use_saved_plans, body.plan_ids)
    settings = get_settings()

    async def events():
        summary_payload = summary.model_dump()
        yield _sse('meta', {'context': summary_payload, 'model_label': settings.deepseek_model_label})
        finished = False
        async for item in llm.stream(body.messages, context):
            if item.get('type') == 'delta':
                yield _sse('delta', {'content': item.get('content', '')})
            elif item.get('type') == 'done':
                finished = True
                yield _sse('done', {**item, 'context': summary_payload})
            else:
                finished = True
                yield _sse('error', {**item, 'context': summary_payload})
        if not finished:
            yield _sse('error', {'detail': '模型未返回完整回答，请重试', 'status': 502,
                                 'context': summary_payload})

    return StreamingResponse(
        events(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@router.get('/context')
def context(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return available_context(db, user)
