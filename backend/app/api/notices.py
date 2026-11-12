"""政策公告与院校资讯（FR-M8-01 / M8-02）。

只读索引：内容来自 app/data/announcements.json（项目整理摘要 + 官方来源链接），
不抓取、不编造；全部接口需登录。
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import current_user
from app.services import notices as notice_service

router = APIRouter(prefix='/notices', tags=['政策与资讯'], dependencies=[Depends(current_user)])


@router.get('')
def list_notices(category: str = Query('', max_length=20), q: str = Query('', max_length=60),
                 limit: int = Query(50, ge=1, le=50)):
    return notice_service.list_notices(category=category, q=q, limit=limit)


@router.get('/{notice_id}')
def notice_detail(notice_id: str):
    item = notice_service.find_notice(notice_id)
    if not item:
        raise HTTPException(404, '公告不存在')
    return notice_service.notice_brief(item)
