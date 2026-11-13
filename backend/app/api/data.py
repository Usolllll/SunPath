from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user
from app.models.entities import User, University, Plan, MajorCatalog
from app.schemas.dto import PROVINCES, SUBJECTS
from app.services import budget, enrichment, readiness as readiness_service, real_data, scoring
from app.services.catalog import load_groups, serialize_group, DISCLAIMER, require_profile
from app.services.recommender import recommend, balanced_plan, ENGINE_VERSION
from app.schemas.matching import AIMatchIn
from app.services.ai_matching import match_universities
from app.services.geography import university_locations

router = APIRouter(tags=['招生数据与智能分析'], dependencies=[Depends(current_user)])

MODE_PATTERN = '^(school|balanced|major)$'


def effective_mode(profile, mode):
    """显式 mode 优先；否则用画像里的 priority_mode（v2 默认 balanced）。"""
    return mode or getattr(profile, 'priority_mode', None) or scoring.DEFAULT_MODE


@router.get('/meta')
def meta(db: Session = Depends(get_db)):
    regions = db.scalars(select(University.region).distinct().order_by(University.region)).all()
    return {
        'provinces': PROVINCES, 'subjects': SUBJECTS, 'regions': list(regions), 'data_year': 2026,
        'history_years': [2023, 2024, 2025], 'disclaimer': DISCLAIMER, 'engine_version': ENGINE_VERSION,
        'modes': [{'key': key, 'label': label, 'weights': scoring.weights(key)} for key, label in scoring.MODE_LABELS.items()],
        'budget_tiers': [{'name': name, 'range': label} for _ceiling, name, label in budget.BUDGET_TIERS],
    }


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
    return {'items': items[(page - 1) * page_size:page * page_size], 'total': len(items), 'universities': university_locations(items), 'regions': regions, 'disclaimer': DISCLAIMER}


@router.get('/catalog/{group_id}')
def detail(group_id: int, province: str = '浙江', year: int = Query(2026, ge=2024, le=2030), db: Session = Depends(get_db)):
    if province not in PROVINCES:
        raise HTTPException(422, '不支持的模拟生源省份')
    group = next((g for g in load_groups(db) if g.id == group_id), None)
    if not group:
        raise HTTPException(404, '专业组不存在')
    return serialize_group(group, province, year, with_plan_trend=True)


@router.get('/recommendations')
def recommendations(mode: str | None = Query(None, pattern=MODE_PATTERN), budget_cap: int | None = Query(None, ge=0, le=2_000_000), user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = require_profile(user)
    active_mode = effective_mode(profile, mode)
    items = real_data.attach_official(db, recommend(db, profile, mode=active_mode, budget_cap=budget_cap), profile.province)
    counts = {risk: sum(x['risk'] == risk for x in items) for risk in ['reach', 'steady', 'safe']}
    return {
        'items': items, 'counts': counts, 'disclaimer': DISCLAIMER, 'engine_version': ENGINE_VERSION,
        'mode': active_mode, 'weights': scoring.weights(active_mode),
        'budget': budget.budget_summary(items, getattr(profile, 'budget_total', None)),
        'budget_cap': budget_cap,
    }


@router.get('/recommendations/compare')
def compare(mode_a: str = Query('school', pattern=MODE_PATTERN), mode_b: str = Query('major', pattern=MODE_PATTERN), count: int = Query(12, ge=3, le=30), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """取舍沙盘：同一候选池、同一配额，两种模式的并排差异（只改同梯度内选择与顺序）。"""
    profile = require_profile(user)
    groups = load_groups(db)
    pool_a = recommend(db, profile, groups=groups, mode=mode_a)
    pool_b = recommend(db, profile, groups=groups, mode=mode_b)
    items_a, missing_a = balanced_plan(pool_a, count)
    items_b, missing_b = balanced_plan(pool_b, count)
    real_data.attach_official(db, items_a, profile.province)
    real_data.attach_official(db, items_b, profile.province)
    diff = scoring.diff_plans(items_a, items_b)
    return {
        'a': {'mode': mode_a, 'label': scoring.MODE_LABELS.get(mode_a, mode_a), 'items': items_a, 'missing_tiers': missing_a},
        'b': {'mode': mode_b, 'label': scoring.MODE_LABELS.get(mode_b, mode_b), 'items': items_b, 'missing_tiers': missing_b},
        'diff': diff, 'summary': scoring.summarize(diff),
        'weights': {'a': scoring.weights(mode_a), 'b': scoring.weights(mode_b)},
        'disclaimer': DISCLAIMER,
    }


@router.post('/recommendations/generate')
def generate(count: int = Query(12, ge=3, le=30), mode: str | None = Query(None, pattern=MODE_PATTERN), user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = require_profile(user)
    active_mode = effective_mode(profile, mode)
    selected, missing = balanced_plan(recommend(db, profile, mode=active_mode), count)
    real_data.attach_official(db, selected, profile.province)
    return {
        'items': selected, 'missing_tiers': missing, 'mode': active_mode, 'weights': scoring.weights(active_mode),
        'budget': budget.budget_summary(selected, getattr(profile, 'budget_total', None)),
        'message': '已按 1:2:1 优先分配冲稳保梯度；不足部分由可用候选补齐。', 'disclaimer': DISCLAIMER,
    }


@router.post('/recommendations/ai')
async def ai_recommendations(body: AIMatchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return await match_universities(db, require_profile(user), body.count)


@router.get('/overview')
def overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {'universities': db.scalar(select(func.count()).select_from(University)), 'groups': len(load_groups(db)), 'plans': db.scalar(select(func.count()).select_from(Plan).where(Plan.user_id == user.id)), 'data_label': '模拟样本 · 2026 招生计划'}


@router.get('/majors')
def majors(db: Session = Depends(get_db)):
    cards = db.scalars(select(MajorCatalog).order_by(MajorCatalog.category, MajorCatalog.name)).all()
    return {'total': len(cards), 'items': [{'name': card.name, 'code': card.code, 'category': card.category,
                                            'major_class': card.major_class, 'riasec_main': card.riasec_main,
                                            'as_of': card.as_of} for card in cards],
            'note': '专业卡为项目自撰摘要，非官方专业介绍；权威介绍见阳光高考专业知识库'}


@router.get('/majors/{name}')
def major_detail(name: str, db: Session = Depends(get_db)):
    card = db.scalar(select(MajorCatalog).where(MajorCatalog.name == name))
    if not card:
        raise HTTPException(404, '该专业暂未收录介绍卡')
    return {'name': card.name, 'code': card.code, 'category': card.category, 'major_class': card.major_class,
            'study_what': card.study_what, 'fit_for': card.fit_for, 'hard_where': card.hard_where,
            'career_where': card.career_where, 'riasec_main': card.riasec_main,
            'riasec_secondary': card.riasec_secondary, 'source': card.source, 'as_of': card.as_of,
            'disclaimer': '内容为项目自撰摘要，非官方专业介绍；不构成录取或就业承诺。'}


@router.get('/options/coverage')
def options_coverage(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """选科覆盖度：当前可报组数 + "再加一门 X" 的反事实可报组数（零数据成本的差异化提示）。"""
    profile = require_profile(user)
    result = readiness_service.coverage(profile, load_groups(db))
    result['disclaimer'] = '按本库模拟专业组统计，不代表全省全部招生计划。'
    return result


@router.get('/groups/{group_id}/readiness')
def group_readiness(group_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """该专业组的"需要准备什么"清单：体检受限提示 + 报名时间线（只读提示）。"""
    profile = require_profile(user)
    group = next((item for item in load_groups(db) if item.id == group_id), None)
    if not group:
        raise HTTPException(404, '专业组不存在')
    return readiness_service.group_readiness(group, profile)


@router.get('/budget/estimate')
def budget_estimate(group_id: int = Query(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """四年总成本明细（学费+住宿费+生活费估算），并给出预算分档与超预算提示。"""
    profile = require_profile(user)
    group = next((item for item in load_groups(db) if item.id == group_id), None)
    if not group:
        raise HTTPException(404, '专业组不存在')
    item = serialize_group(group, profile.province, profile.exam_year)
    cost = budget.four_year_cost(item)
    budget_total = getattr(profile, 'budget_total', None)
    return {'group_id': group.id, 'university': item['university']['name'], 'cost': cost,
            'tier': budget.budget_tier(cost['total']), 'budget_total': budget_total,
            'over_budget': bool(budget_total and cost['total'] > budget_total),
            'over_by': max(0, cost['total'] - budget_total) if budget_total else 0,
            'disclaimer': '生活费为按城市等级的估算值（非官方数据）；学费/住宿费来自采集字段，正式填报请以招生章程为准。'}

# ---------------------------------------------------------------- 真实投档数据（官方来源，只读）
def _real_provinces(db: Session) -> list[str]:
    """已收录的官方真实数据省份（随导入动态变化，不再写死）。"""
    return [item['province'] for item in real_data.summary(db)['provinces']]


@router.get('/real-data/summary')
def real_data_summary(db: Session = Depends(get_db)):
    """真实投档数据覆盖情况：省份、行数、年份、当前数据版本（含来源与发布时间）。"""
    return real_data.summary(db)


@router.get('/real-data/rows')
def real_data_rows(province: str = Query(...), year: int | None = Query(None, ge=2020, le=2030),
                   q: str = Query('', max_length=40), page: int = Query(1, ge=1),
                   page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    if province not in _real_provinces(db):
        raise HTTPException(422, '该省的官方投档数据尚未收录')
    return real_data.list_rows(db, province, year, q, page, page_size)


@router.get('/real-data/school')
def real_data_school(name: str = Query(..., min_length=1, max_length=80), province: str = Query(...),
                     db: Session = Depends(get_db)):
    if province not in _real_provinces(db):
        raise HTTPException(422, '该省的官方投档数据尚未收录')
    official = real_data.school_official(db, name, province)
    if not official:
        raise HTTPException(404, '该院校在本库真实数据中暂无记录')
    rows = real_data.list_rows(db, province, official['exam_year'], name, 1, 20)
    return {'school_name': name, 'official': official, 'recent_rows': rows['items'],
            'disclaimer': '真实投档线仅作核对参考，不等于录取线，也不代表今年录取结果。'}


# ---------------------------------------------------------------- 一分一段（位次参考，示例数据）
from app.services import score_segment as score_segment_service  # noqa: E402  （追加在文件末尾，避免改动已有导入）


@router.get('/score-segment')
def score_segment_lookup(province: str = Query(..., min_length=2, max_length=20),
                         year: int = Query(..., ge=2020, le=2030),
                         score: int = Query(..., ge=0, le=750)):
    """按省份/年份/分数查一分一段的累计人数与位次参考；示例数据，不预测录取结果。"""
    data = score_segment_service.query(province, year, score)
    if data is None:
        if score_segment_service.dataset(province, year) is None:
            raise HTTPException(404, '该省未收录一分一段数据')
        raise HTTPException(404, '该分数段未收录')
    data['disclaimer'] = '一分一段数据用于位次参考，不代表录取结果。'
    return data


@router.get('/score-segment/segments')
def score_segment_segments(province: str = Query(..., min_length=2, max_length=20),
                           year: int = Query(..., ge=2020, le=2030),
                           limit: int = Query(60, ge=1, le=200)):
    """返回该省该年一分一段分段列表（分数降序，最多 limit 条）+ 数据来源与示例标识。"""
    data = score_segment_service.segments(province, year, limit)
    if data is None:
        raise HTTPException(404, '该省未收录一分一段数据')
    data['disclaimer'] = '一分一段数据用于位次参考，不代表录取结果。'
    return data
