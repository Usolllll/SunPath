from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user
from app.models.entities import Plan, User
from app.schemas.dto import PlanIn, ProfileIn
from app.services.catalog import require_profile
from app.services.recommender import recommend
from app.utils.export import plan_csv

router = APIRouter(prefix='/plans', tags=['志愿方案'])

def serialize_plan(plan):
    return {'id': plan.id, 'name': plan.name, 'items': plan.items, 'profile_snapshot': plan.profile_snapshot, 'created_at': plan.created_at.isoformat(), 'updated_at': plan.updated_at.isoformat()}

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

@router.get('')
def list_plans(user: User = Depends(current_user), db: Session = Depends(get_db)):
    plans = db.scalars(select(Plan).where(Plan.user_id == user.id).order_by(Plan.updated_at.desc())).all()
    return [serialize_plan(p) for p in plans]

@router.post('', status_code=201)
def create(body: PlanIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    items, profile = build_snapshot(db, user, body)
    plan = Plan(user_id=user.id, name=body.name, items=items, profile_snapshot=profile)
    db.add(plan)
    db.commit()
    return serialize_plan(plan)

@router.get('/{plan_id}')
def get_plan(plan_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return serialize_plan(owned_plan(db, user, plan_id))

@router.put('/{plan_id}')
def update(plan_id: int, body: PlanIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = owned_plan(db, user, plan_id)
    plan.items, plan.profile_snapshot = build_snapshot(db, user, body)
    plan.name = body.name
    db.commit()
    return serialize_plan(plan)

@router.delete('/{plan_id}', status_code=204)
def delete(plan_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned_plan(db, user, plan_id))
    db.commit()

@router.get('/{plan_id}/export')
def export(plan_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = owned_plan(db, user, plan_id)
    return Response(content=plan_csv(plan).encode('utf-8'), media_type='text/csv; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="sunpath-plan-{plan.id}.csv"'})
