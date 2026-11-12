"""站内消息中心（FR-M8-03 / M8-05）。

全部接口需登录且只操作本人消息；refresh 按订阅偏好生成提醒（dedupe_key 幂等）。
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_user
from app.models.entities import User
from app.services import notices as notice_service

router = APIRouter(prefix='/messages', tags=['消息中心'])


class SubscriptionIn(BaseModel):
    """订阅偏好：类型子集 + 站内信渠道 + 提前提醒天数。"""
    types: list[Literal['collection', 'policy', 'lecture', 'quality', 'plan', 'result']] = Field(default_factory=list,
                                                                                        max_length=5)
    channel: Literal['site'] = 'site'
    lead_days: int = Field(default=3, ge=0, le=14)


@router.get('')
def list_messages(only_unread: bool = Query(False), user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    return notice_service.list_messages(db, user, only_unread=only_unread)


@router.get('/unread-count')
def unread_count(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {'unread': notice_service.unread_count(db, user)}


@router.post('/refresh')
def refresh(user: User = Depends(current_user), db: Session = Depends(get_db)):
    result = notice_service.refresh(db, user)
    db.commit()
    return result


@router.post('/read-all')
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    updated = notice_service.mark_all_read(db, user)
    db.commit()
    return {'updated': updated}


@router.get('/subscription')
def get_subscription(user: User = Depends(current_user)):
    return notice_service.current_subscription(user)


@router.put('/subscription')
def save_subscription(body: SubscriptionIn, user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    profile = getattr(user, 'profile', None)
    if not profile:
        raise HTTPException(400, '请先完善考生画像后再设置订阅')
    value = notice_service.normalize_subscription(body.model_dump())
    profile.subscription = value
    db.commit()
    return value


@router.post('/{message_id}/read')
def read_message(message_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    message = notice_service.get_owned_message(db, user, message_id)
    if not message:
        raise HTTPException(404, '消息不存在')
    notice_service.mark_read(db, message)
    db.commit()
    return {'read': True}
