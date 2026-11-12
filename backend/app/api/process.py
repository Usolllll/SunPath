"""录取进程与结果查询（FR-M7-01 / M7-02 / M7-03 / M7-05）：批次时间轴、模拟投档结果、结果导出。

说明：无真实录取结果，模拟投档仅基于已收录的官方投档线做"是否达到最低位次"的演示判定，
不代表录取概率或录取结果；所有接口均需登录，方案结果仅属主可见。
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_user
from app.models.entities import Plan, User
from app.services import audit
from app.services import process as process_service

router = APIRouter(prefix='/process', tags=['录取进程与结果'])


def _owned_plan(db: Session, user: User, plan_id: int) -> Plan:
    plan = db.scalar(select(Plan).where(Plan.id == plan_id, Plan.user_id == user.id))
    if not plan:
        raise HTTPException(404, '方案不存在')
    return plan


def _province(user: User, province: str) -> str:
    """显式 province 优先；否则用画像省份；再缺省回退浙江。"""
    province = (province or '').strip()
    if province:
        return province
    profile = getattr(user, 'profile', None)
    return (getattr(profile, 'province', None) or '浙江')


@router.get('/schedule')
def schedule(province: str = Query('', max_length=20), user: User = Depends(current_user)):
    """录取批次时间轴；province 未收录时回退通用时间轴并在 note 标注。"""
    return process_service.schedule(_province(user, province))


@router.get('/collection')
def collection(province: str = Query('', max_length=20), user: User = Depends(current_user)):
    """征集志愿时间窗与倒计时（基于时间轴中「征集志愿」事件）。"""
    return process_service.collection(_province(user, province))


@router.get('/results/{plan_id}')
def results(plan_id: int, request: Request,
            user: User = Depends(current_user), db: Session = Depends(get_db)):
    """模拟投档结果：仅属主可见；只做官方投档最低位次的达到/未达到判定。"""
    plan = _owned_plan(db, user, plan_id)
    result = process_service.simulate(db, plan, getattr(user, 'profile', None))
    audit.log_action(db, user, 'result.query', target=f'plan:{plan.id}',
                     detail={'summary': result['summary']}, request=request)
    db.commit()
    return result


@router.get('/results/{plan_id}/export')
def export(plan_id: int, request: Request,
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    """导出模拟投档结果 CSV（UTF-8 BOM；safe_cell 防公式注入）。"""
    plan = _owned_plan(db, user, plan_id)
    result = process_service.simulate(db, plan, getattr(user, 'profile', None))
    audit.log_action(db, user, 'result.export', target=f'plan:{plan.id}',
                     detail={'format': 'csv', 'total': result['summary']['total']}, request=request)
    db.commit()
    return Response(
        content=process_service.result_csv(result).encode('utf-8'),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="sunpath-result-{plan.id}.csv"'},
    )
