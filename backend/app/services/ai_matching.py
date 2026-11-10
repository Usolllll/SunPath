"""AI chooses IDs; trusted application code controls eligibility, counts, risk and facts."""
from collections import Counter
from pathlib import Path
from fastapi import HTTPException
from pydantic import ValidationError
from app.schemas.dto import ProfileIn
from app.schemas.matching import AISelection, AIMatchIn
from app.services import llm
from app.services.catalog import load_groups, serialize_group, DISCLAIMER
from app.services.recommender import recommend, balanced_plan

SKILL_PATH = Path(__file__).resolve().parents[1] / 'skills' / 'match-universities' / 'SKILL.md'
ENGINE_VERSION = 'skill-deepseek-match-v1'
RISKS = ['reach', 'steady', 'safe']


def load_skill():
    source = SKILL_PATH.read_text(encoding='utf-8')
    return source.split('---', 2)[-1].strip()


def selection_context(db, profile, count):
    try:
        count = AIMatchIn(count=count).count
    except ValidationError:
        raise HTTPException(422, '推荐数量必须是 3–30 之间的整数') from None
    try:
        profile = ProfileIn.model_validate(profile)
    except ValidationError:
        raise HTTPException(400, '考生画像超出有效范围，请检查分数、位次和选科') from None
    groups = load_groups(db)
    if len(groups) > 500:
        raise HTTPException(413, '当前院校库超过单次匹配容量，请先缩小院校范围')
    eligible = recommend(db, profile, groups=groups, mode=(getattr(profile, 'priority_mode', None) or 'balanced'))
    reference, _ = balanced_plan(eligible, count)
    quotas = {risk: sum(item['risk'] == risk for item in reference) for risk in RISKS}
    by_id = {item['id']: item for item in eligible}
    catalog = []
    for group in groups:
        item = by_id.get(group.id) or serialize_group(group, profile.province, profile.exam_year)
        catalog.append({
            'group_id': item['id'], 'code': item['code'], 'group_name': item['name'],
            'university': {key: item['university'][key] for key in ('id', 'name', 'city', 'region', 'level', 'category', 'description')},
            'majors': item['majors'], 'required_subjects': item['required_subjects'],
            'tuition': item['tuition'], 'history': item['history'], 'seats': item['seats'],
            'province': item['province'], 'year': item['year'], 'eligible': item['id'] in by_id,
            **{key: item[key] for key in ('risk', 'baseline_rank', 'rank_ratio', 'history_rank_min', 'history_rank_max', 'volatility') if key in item},
        })
    target = min(count, len(eligible))
    context = {
        # 只提供模型选择所需的最小画像；预算/体检/兴趣分不进 AI 上下文
        'candidate_profile': {key: profile.model_dump()[key] for key in
                              ('province', 'exam_year', 'score', 'rank', 'subjects', 'regions', 'majors', 'priority_mode')
                              if key in profile.model_dump()},
        'data_label': '全部录取与计划资料为模拟样本',
        'limits': {'requested_count': count, 'required_count': target, 'minimum_count': min(3, len(eligible)), 'maximum_count': min(30, len(eligible))},
        'risk_quotas': quotas, 'eligible_group_ids': list(by_id), 'catalog': catalog,
        'eligible_buckets': {risk: {'required_count': quotas[risk], 'allowed_ids': [item['id'] for item in eligible if item['risk'] == risk]} for risk in RISKS},
    }
    return context, by_id


def validate_selection(raw, context, by_id):
    try:
        selection = AISelection.model_validate(raw)
    except ValidationError:
        raise HTTPException(502, 'AI 匹配格式未通过校验，请重新匹配') from None
    ids = selection.group_ids
    if len(ids) != context['limits']['required_count'] or len(set(ids)) != len(ids):
        raise HTTPException(502, 'AI 匹配数量不符合要求或含重复专业组，请重新匹配')
    if any(group_id not in by_id for group_id in ids):
        raise HTTPException(502, 'AI 返回了未收录或不符合条件的专业组，结果已拒绝，请重新匹配')
    selected = [by_id[group_id] for group_id in ids]
    actual = Counter(item['risk'] for item in selected)
    if any(actual[risk] != context['risk_quotas'][risk] for risk in RISKS):
        raise HTTPException(502, 'AI 返回的冲稳保数量不符合约束，结果已拒绝，请重新匹配')
    selected.sort(key=lambda item: RISKS.index(item['risk']))
    return selected


async def match_universities(db, profile, count=12):
    context, by_id = selection_context(db, profile, count)
    attempts = 0
    if by_id:
        skill = load_skill()
        for attempt in range(2):
            attempts += 1
            raw, result = await llm.complete_json(skill, context)
            try:
                selected = validate_selection(raw, context, by_id)
                break
            except HTTPException as error:
                if attempt == 1:
                    raise
                previous = raw.get('group_ids', [])
                previous = [value for value in previous[:30] if type(value) is int] if isinstance(previous, list) else []
                context['validation_feedback'] = {
                    'error': error.detail, 'previous_group_ids': previous,
                    'previous_risk_counts': dict(Counter(by_id[value]['risk'] for value in previous if value in by_id)),
                    'instruction': '重新从 eligible_buckets 的每个 allowed_ids 列表中分别选取 required_count 个不重复 ID，再按 reach、steady、safe 顺序拼接。不能修改梯度或数量。',
                }
        model_label = result.model_label
    else:
        selected, model_label = [], None
    counts = {risk: sum(item['risk'] == risk for item in selected) for risk in RISKS}
    below_minimum = len(selected) < 3
    return {
        'items': selected, 'counts': counts, 'disclaimer': DISCLAIMER, 'engine_version': ENGINE_VERSION,
        'ai_selection': {
            'model_label': model_label, 'skill': 'match-universities', 'requested_count': count,
            'attempts': attempts,
            'selected_count': len(selected), 'eligible_count': len(by_id),
            'catalog_universities': len({item['university']['id'] for item in context['catalog']}),
            'catalog_groups': len(context['catalog']), 'selected_universities': len({item['university']['id'] for item in selected}),
            'minimum_count': 3, 'maximum_count': 30, 'below_minimum': below_minimum,
            'missing_tiers': [risk for risk in RISKS if not counts[risk]],
            'message': ('符合条件的候选不足 3 个，已仅返回实际可选项，没有为凑数放宽条件。' if below_minimum else f'已从数据库候选中由 AI 精选 {len(selected)} 个专业组，数量、选科、位次与梯度已通过后端校验。'),
        },
    }
