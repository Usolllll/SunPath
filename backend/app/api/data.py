from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user
from app.models.entities import User, University, Plan
from app.schemas.dto import PROVINCES, SUBJECTS
from app.services.catalog import load_groups, serialize_group, DISCLAIMER, require_profile
from app.services.recommender import recommend, balanced_plan, ENGINE_VERSION

router = APIRouter(tags=['招生数据与智能分析'], dependencies=[Depends(current_user)])

@router.get('/meta')
def meta():
    return {'provinces': PROVINCES, 'subjects': SUBJECTS, 'data_year': 2026, 'history_years': [2023, 2024, 2025], 'disclaimer': DISCLAIMER, 'engine_version': ENGINE_VERSION}

@router.get('/catalog')
def catalog(q: str = Query('', max_length=80), region: str = '', level: str = '', subject: str = '', province: str = '浙江', year: int = Query(2026, ge=2024, le=2030), page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=100), db: Session = Depends(get_db)):
    if province not in PROVINCES:
        raise HTTPException(422, '不支持的模拟生源省份')
    items = []
    groups = load_groups(db)
    for group in groups:
        u = group.university
        if q and q.lower() not in (' '.join([u.name, group.name, *group.majors])).lower():
            continue
        if region and u.region != region or level and level not in u.level or subject and subject not in group.required_subjects:
            continue
        items.append(serialize_group(group, province, year))
    regions = sorted(set(g.university.region for g in groups))
    return {'items': items[(page - 1) * page_size:page * page_size], 'total': len(items), 'regions': regions, 'disclaimer': DISCLAIMER}

@router.get('/catalog/{group_id}')
def detail(group_id: int, province: str = '浙江', year: int = Query(2026, ge=2024, le=2030), db: Session = Depends(get_db)):
    if province not in PROVINCES:
        raise HTTPException(422, '不支持的模拟生源省份')
    group = next((g for g in load_groups(db) if g.id == group_id), None)
    if not group:
        raise HTTPException(404, '专业组不存在')
    return serialize_group(group, province, year)

@router.get('/recommendations')
def recommendations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = recommend(db, require_profile(user))
    counts = {risk: sum(x['risk'] == risk for x in items) for risk in ['reach', 'steady', 'safe']}
    return {'items': items, 'counts': counts, 'disclaimer': DISCLAIMER, 'engine_version': ENGINE_VERSION}

@router.post('/recommendations/generate')
def generate(count: int = Query(12, ge=3, le=30), user: User = Depends(current_user), db: Session = Depends(get_db)):
    selected, missing = balanced_plan(recommend(db, require_profile(user)), count)
    return {'items': selected, 'missing_tiers': missing, 'message': '已按 1:2:1 优先分配冲稳保梯度；不足部分由可用候选补齐。', 'disclaimer': DISCLAIMER}

@router.get('/overview')
def overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {'universities': db.scalar(select(func.count()).select_from(University)), 'groups': len(load_groups(db)), 'plans': db.scalar(select(func.count()).select_from(Plan).where(Plan.user_id == user.id)), 'data_label': '模拟样本 · 2026 招生计划'}
