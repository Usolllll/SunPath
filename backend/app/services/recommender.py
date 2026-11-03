"""Authoritative eligibility/risk checks; AI selection cannot bypass these rules."""
from app.services.catalog import load_groups, serialize_group

ENGINE_VERSION = 'rank-rules-v1'

def recommend(db, profile, groups=None):
    results = []
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
        item.update(risk=risk, baseline_rank=baseline, history_rank_min=min(ranks), history_rank_max=max(ranks), rank_ratio=round(ratio, 4), volatility=volatility, reasons=reasons, warnings=warnings,
                    preference_matches=int(region_match) + int(major_match))
        results.append(item)
    # Preference matches first; within ties choose nearest rank reference. Never treat the score as a probability.
    results.sort(key=lambda x: (-x['preference_matches'], abs(x['rank_ratio'] - 0.95), x['id']))
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
