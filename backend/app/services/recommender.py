"""Authoritative eligibility/risk checks; AI selection cannot bypass these rules.

v2：新增「取舍沙盘」模式（school / balanced / major）与预算上限。模式**只改变同一梯度内的
选择与顺序**，绝不改变候选池（哪些组合格）与冲稳保配额；缺省 mode 时回退一期排序行为。

v3：每个 item 增加 `physical_flags`（体检受限提示，复用 readiness 规则）。只增加提示字段，
**不参与**候选池过滤、配额、打分与排序；无体检数据时为空数组。
"""
from app.services import budget, enrichment, readiness, scoring
from app.services.catalog import load_groups, serialize_group

ENGINE_VERSION = 'rank-rules-v2'


def _cost(item):
    return budget.four_year_cost(item)


def physical_flags(group, profile, rules=None):
    """体检受限提示：命中 red/yellow 规则且专业组含 blocked_keywords 时给出提示；只提示不过滤。"""
    info = readiness.group_readiness(group, profile, rules)
    return [{'level': entry.get('level', 'red'), 'label': entry.get('label'), 'text': entry.get('text')}
            for entry in info['blockers'] + info['warnings']]


def recommend(db, profile, groups=None, mode=None, budget_cap=None, include_cost=True):
    results = []
    interests = getattr(profile, 'interests', None)
    rules = enrichment.readiness_rules()
    for group in (load_groups(db) if groups is None else groups):
        if not set(group.required_subjects).issubset(set(profile.subjects)):
            continue
        item = serialize_group(group, profile.province, profile.exam_year)
        if not item['history'] or item['seats'] <= 0:
            continue
        if any(not (1 <= h['rank'] <= 2_000_000 and 0 <= h['score'] <= 750) for h in item['history']):
            continue
        ranks = [h['rank'] for h in item['history']]
        weights = list(range(1, len(ranks) + 1))
        baseline = round(sum(r * w for r, w in zip(ranks, weights)) / sum(weights))
        ratio = profile.rank / baseline
        if ratio > 1.35:
            continue
        risk = 'safe' if ratio <= 0.8 else ('steady' if ratio <= 1.08 else 'reach')
        region_match = group.university.region in profile.regions
        major_match = any(pref in major for pref in profile.majors for major in group.majors)
        volatility = round((max(ranks) - min(ranks)) / baseline * 100, 1)
        reasons = [f'你的位次 {profile.rank:,}，近三年加权参考位次 {baseline:,}', '符合专业组选科要求' if group.required_subjects else '专业组不限选科']
        if region_match:
            reasons.append('符合你的目标地区偏好')
        if major_match:
            reasons.append('包含你感兴趣的专业方向')
        warnings = ['模拟数据估算，不代表录取概率', '冲刺梯度，建议搭配稳妥与保底志愿' if risk == 'reach' else '录取位次可能随招生计划和报考热度变化']
        if volatility > 12:
            warnings.append(f'历史位次波动 {volatility}%，需重点关注')
        item.update(risk=risk, baseline_rank=baseline, history_rank_min=min(ranks), history_rank_max=max(ranks),
                    rank_ratio=round(ratio, 4), volatility=volatility, reasons=reasons, warnings=warnings,
                    preference_matches=int(region_match) + int(major_match))
        item['physical_flags'] = physical_flags(group, profile, rules)
        if include_cost:
            item['cost'] = _cost(item)
        if mode is not None:
            item.update(scoring.score_item(item, profile, mode, interests))
        results.append(item)

    if mode is None:
        # 一期行为（兼容路径）：偏好命中优先，其次最接近参考位次
        results.sort(key=lambda x: (-x['preference_matches'], abs(x['rank_ratio'] - 0.95), x['id']))
    else:
        results.sort(key=lambda x: (-x['total_score'], abs(x['rank_ratio'] - 0.95), x['id']))

    if budget_cap:
        # 硬筛：只在调用方显式要求时过滤；默认不隐藏，避免信息茧房
        results = [item for item in results if not item.get('cost') or item['cost']['total'] <= budget_cap]
    return results


def balanced_plan(items, count=12):
    buckets = {risk: [x for x in items if x['risk'] == risk] for risk in ['reach', 'steady', 'safe']}
    reach = max(1, count // 4)
    steady = max(1, count // 2)
    quotas = {'reach': reach, 'steady': steady, 'safe': max(0, count - reach - steady)}
    selected = [x for risk, bucket in buckets.items() for x in bucket[:quotas[risk]]]
    selected_ids = {x['id'] for x in selected}
    selected += [x for x in items if x['id'] not in selected_ids][:max(0, count - len(selected))]
    selected.sort(key=lambda x: ['reach', 'steady', 'safe'].index(x['risk']))
    missing = [risk for risk, bucket in buckets.items() if not bucket]
    return selected, missing
