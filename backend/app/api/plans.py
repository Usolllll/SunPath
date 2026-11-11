"""志愿方案生命周期：草稿/提交/撤回、批次、创建幂等与导出审计。

v3 语义：
- 方案有 batch（本科批/专科批）与 status（draft/submitted）；
- 已提交（submitted）方案不可编辑/删除（409），需先撤回；
- submit 幂等：重复提交直接返回当前状态（200），只有首次提交做当前画像重校验并写审计；
- POST 创建支持 Idempotency-Key 请求头（1–64 字符），同一用户同一 key 直接返回已有方案（200）。
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_user
from app.models.entities import Plan, User
from app.schemas.dto import PlanIn, ProfileIn
from app.services.audit import log_action
from app.services.catalog import require_profile
from app.services.recommender import recommend
from app.utils.export import plan_csv

router = APIRouter(prefix='/plans', tags=['志愿方案'])

DRAFT = 'draft'
SUBMITTED = 'submitted'


def iso_utc(value):
    """SQLite 读回的 datetime 不带时区；统一按 UTC 输出，保证同一记录多次读取序列化一致。"""
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


def serialize_plan(plan):
    return {
        'id': plan.id, 'name': plan.name, 'items': plan.items, 'profile_snapshot': plan.profile_snapshot,
        'batch': plan.batch or '本科批', 'status': plan.status or DRAFT,
        'submitted_at': iso_utc(plan.submitted_at),
        'idempotency_key': plan.idempotency_key,
        'created_at': iso_utc(plan.created_at), 'updated_at': iso_utc(plan.updated_at),
    }


def owned_plan(db, user, plan_id):
    plan = db.scalar(select(Plan).where(Plan.id == plan_id, Plan.user_id == user.id))
    if not plan:
        raise HTTPException(404, '方案不存在')
    return plan


def build_snapshot(db, user, body):
    profile = require_profile(user)
    available = {item['id']: item for item in recommend(db, profile)}
    invalid = [i for i in body.group_ids if i not in available]
    if invalid:
        raise HTTPException(400, '部分专业组不符合当前画像、位次或招生要求，请重新匹配后调整')
    return [available[i] for i in body.group_ids], ProfileIn.model_validate(profile, from_attributes=True).model_dump()


def ensure_editable(plan):
    if (plan.status or DRAFT) != DRAFT:
        raise HTTPException(409, '已提交的方案不可编辑，请先撤回')


@router.get('')
def list_plans(user: User = Depends(current_user), db: Session = Depends(get_db)):
    plans = db.scalars(select(Plan).where(Plan.user_id == user.id).order_by(Plan.updated_at.desc())).all()
    return [serialize_plan(p) for p in plans]


@router.post('', status_code=201)
def create(body: PlanIn, response: Response, request: Request,
           idempotency_key: str | None = Header(None, alias='Idempotency-Key', min_length=1, max_length=64),
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    if idempotency_key:
        existing = db.scalar(select(Plan).where(Plan.user_id == user.id, Plan.idempotency_key == idempotency_key))
        if existing:
            # 同一用户同一 key：幂等返回已有方案，不重复创建
            response.status_code = 200
            return serialize_plan(existing)
    items, profile = build_snapshot(db, user, body)
    plan = Plan(user_id=user.id, name=body.name, items=items, profile_snapshot=profile,
                batch=body.batch, status=DRAFT, idempotency_key=idempotency_key)
    db.add(plan)
    db.flush()
    log_action(db, user, 'plan.create', target=f'plan:{plan.id}',
               detail={'batch': body.batch, 'item_count': len(items)}, request=request)
    db.commit()
    return serialize_plan(plan)


@router.get('/{plan_id}')
def get_plan(plan_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return serialize_plan(owned_plan(db, user, plan_id))


@router.put('/{plan_id}')
def update(plan_id: int, body: PlanIn, request: Request,
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = owned_plan(db, user, plan_id)
    ensure_editable(plan)
    plan.items, plan.profile_snapshot = build_snapshot(db, user, body)
    plan.name = body.name
    plan.batch = body.batch
    log_action(db, user, 'plan.update', target=f'plan:{plan.id}',
               detail={'batch': body.batch, 'item_count': len(plan.items)}, request=request)
    db.commit()
    return serialize_plan(plan)


@router.delete('/{plan_id}', status_code=204)
def delete(plan_id: int, request: Request,
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = owned_plan(db, user, plan_id)
    if (plan.status or DRAFT) != DRAFT:
        raise HTTPException(409, '已提交的方案不可删除，请先撤回')
    log_action(db, user, 'plan.delete', target=f'plan:{plan.id}',
               detail={'batch': plan.batch, 'item_count': len(plan.items or [])}, request=request)
    db.delete(plan)
    db.commit()


@router.post('/{plan_id}/submit')
def submit(plan_id: int, request: Request,
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = owned_plan(db, user, plan_id)
    if (plan.status or DRAFT) == SUBMITTED:
        # 重复提交：幂等返回当前状态，不重复写审计
        return serialize_plan(plan)
    profile = require_profile(user)
    available = {item['id'] for item in recommend(db, profile)}
    invalid = [item.get('id') for item in (plan.items or []) if item.get('id') not in available]
    if invalid:
        raise HTTPException(400, '方案中有专业组不符合当前画像、位次或招生要求，请重新匹配后调整')
    plan.status = SUBMITTED
    plan.submitted_at = datetime.now(timezone.utc)
    log_action(db, user, 'plan.submit', target=f'plan:{plan.id}',
               detail={'batch': plan.batch, 'item_count': len(plan.items or [])}, request=request)
    db.commit()
    return serialize_plan(plan)


@router.post('/{plan_id}/withdraw')
def withdraw(plan_id: int, request: Request,
             user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = owned_plan(db, user, plan_id)
    if (plan.status or DRAFT) != SUBMITTED:
        raise HTTPException(400, '该方案尚未提交，无需撤回')
    plan.status = DRAFT
    plan.submitted_at = None
    log_action(db, user, 'plan.withdraw', target=f'plan:{plan.id}',
               detail={'batch': plan.batch}, request=request)
    db.commit()
    return serialize_plan(plan)


@router.get('/{plan_id}/export')
def export(plan_id: int, request: Request,
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = owned_plan(db, user, plan_id)
    log_action(db, user, 'plan.export', target=f'plan:{plan.id}',
               detail={'format': 'csv', 'status': plan.status or DRAFT}, request=request)
    db.commit()
    return Response(content=plan_csv(plan).encode('utf-8'), media_type='text/csv; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="sunpath-plan-{plan.id}.csv"'})
