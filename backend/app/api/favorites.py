"""院校收藏（FR-M5-05）。

全部接口需登录，且严格按 user_id 做属主隔离：只能看到/删除自己的收藏。
新增/删除写审计（favorite.add / favorite.remove），由调用方统一 commit。
"""
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_user
from app.models.entities import Favorite, University, User
from app.schemas.dto import FavoriteIn
from app.services.audit import log_action

router = APIRouter(prefix='/favorites', tags=['院校收藏'])

UNIVERSITY_KEYS = ('id', 'name', 'city', 'region', 'level', 'level_tier', 'category')


def iso_utc(value):
    """SQLite 读回的 datetime 不带时区；统一按 UTC 输出，保证重复请求序列化一致。"""
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


def serialize_favorite(favorite, university):
    return {
        'id': favorite.id,
        'university': {key: getattr(university, key) for key in UNIVERSITY_KEYS},
        'created_at': iso_utc(favorite.created_at),
    }


def owned_favorite(db, user, university_id):
    favorite = db.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.university_id == university_id))
    if not favorite:
        raise HTTPException(404, '未收藏该院校')
    return favorite


@router.get('')
def list_favorites(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Favorite, University)
        .join(University, University.id == Favorite.university_id)
        .where(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc(), Favorite.id.desc())
    ).all()
    return [serialize_favorite(favorite, university) for favorite, university in rows]


@router.get('/ids')
def favorite_ids(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ids = db.scalars(
        select(Favorite.university_id)
        .where(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc(), Favorite.id.desc())
    ).all()
    return {'ids': list(ids)}


@router.post('', status_code=201)
def add_favorite(body: FavoriteIn, response: Response, request: Request,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    university = db.get(University, body.university_id)
    if not university:
        raise HTTPException(404, '院校不存在')
    existing = db.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.university_id == body.university_id))
    if existing:
        # 重复收藏：幂等返回已有记录（200，不再写审计、不重复插入）
        response.status_code = 200
        return serialize_favorite(existing, university)
    favorite = Favorite(user_id=user.id, university_id=body.university_id)
    db.add(favorite)
    try:
        db.flush()
    except IntegrityError:
        # 并发重复收藏：(user_id, university_id) 唯一约束兜底，回滚后按幂等返回已有记录
        db.rollback()
        existing = db.scalar(select(Favorite).where(Favorite.user_id == user.id,
                                                    Favorite.university_id == body.university_id))
        if existing:
            response.status_code = 200
            return serialize_favorite(existing, db.get(University, body.university_id))
        raise HTTPException(409, '收藏状态已变化，请刷新后重试')
    log_action(db, user, 'favorite.add', target=f'university:{university.id}',
               detail={'favorite_id': favorite.id}, request=request)
    db.commit()
    return serialize_favorite(favorite, university)


@router.delete('/{university_id}', status_code=204)
def remove_favorite(university_id: int, request: Request,
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    favorite = owned_favorite(db, user, university_id)
    log_action(db, user, 'favorite.remove', target=f'university:{university_id}',
               detail={'favorite_id': favorite.id}, request=request)
    db.delete(favorite)
    db.commit()
    return Response(status_code=204)
