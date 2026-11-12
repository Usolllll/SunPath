"""留学规划（FR-M11-01）：官方入口索引 + 个人路径目标（全部需登录、仅本人）。

- ``GET /options``：2 个考试、4 个地区、18 所学校（官方入口 + 高考接受情况 + 资格路径）；
- ``GET /target``：本人已保存的留学目标与规划（语言三态 / path 差异化清单与时间线）；
- ``PUT /target``：保存目标（严格校验地区/学校/考试/分数/路径），写审计 ``study_abroad.save``；
- ``DELETE /target``：清除目标，写审计 ``study_abroad.clear``。

文案边界：只做官方入口索引与通用提示，不出现录取概率，不代填申请表。
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_user
from app.models.entities import User
from app.services import audit
from app.services import study_abroad as study_service

router = APIRouter(prefix='/study-abroad', tags=['留学规划'], dependencies=[Depends(current_user)])


class TargetIn(BaseModel):
    region: str = Field(min_length=1, max_length=20)
    school_id: str = Field(min_length=1, max_length=40)
    test_type: Literal['ielts', 'toefl']
    test_score: float
    target_major: str | None = None
    path: Literal['gaokao', 'post_gaokao', 'international'] = 'gaokao'
    gaokao_score: float | None = None


@router.get('/options')
def get_options():
    return study_service.options()


@router.get('/target')
def get_target(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return study_service.target_view(db, user)


@router.put('/target')
def save_target(body: TargetIn, request: Request, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    try:
        study_service.save_target(db, user, body.model_dump())
    except study_service.StudyAbroadValidationError as error:
        db.rollback()
        raise HTTPException(400, str(error)) from None
    audit.log_action(db, user, 'study_abroad.save', target=f'school:{body.school_id}',
                     detail={'region': body.region, 'school_id': body.school_id,
                             'test_type': body.test_type},
                     request=request)
    db.commit()
    return study_service.target_view(db, user)


@router.delete('/target', status_code=204)
def clear_target(request: Request, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    existed = study_service.clear_target(db, user)
    audit.log_action(db, user, 'study_abroad.clear', target='study_abroad',
                     detail={'existed': existed}, request=request)
    db.commit()
    return Response(status_code=204)
