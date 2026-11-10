"""报考准备清单（只读提示）：选科覆盖度、体检受限提示、报名时间线。

边界：仅提示，不构成报考资格认定；每条规则都带来源；缺数据时显示"未收录"，不推测。
"""
from app.services import enrichment

DISCLAIMER = '以下为提示性清单，不构成报考资格认定；最终以省考试院、高校招生章程与体检结论为准。'


def coverage(profile, groups) -> dict:
    """选科覆盖度：当前可报组数，以及"再加一门 X"后的反事实可报组数。"""
    chosen = set(profile.subjects or [])
    base = [group for group in groups if set(group.required_subjects or []).issubset(chosen)]
    options = []
    for subject in ('物理', '化学', '生物', '历史', '政治', '地理'):
        if subject in chosen:
            continue
        extended = chosen | {subject}
        extra = [group for group in groups if set(group.required_subjects or []).issubset(extended)]
        options.append({'subject': subject, 'groups': len(extra), 'gain': len(extra) - len(base)})
    options.sort(key=lambda item: (-item['gain'], item['subject']))
    return {'chosen': sorted(chosen), 'base_groups': len(base), 'options': options}


def _triggered(rule, physical) -> bool:
    if not physical:
        return False
    condition = rule['condition']
    if physical.get(condition) is True:
        return True
    if condition == 'naked_vision_lt_5_0':
        value = physical.get('naked_vision')
        return value is not None and float(value) < 5.0
    if condition == 'corrected_vision_gt_400':
        value = physical.get('corrected_vision')
        return value is not None and float(value) > 400
    return False


def _match_majors(rule, majors) -> list[str]:
    names = [str(major) for major in (majors or [])]
    hits = [name for name in names if any(keyword in name for keyword in rule.get('blocked_keywords') or [])]
    return hits


def group_readiness(group, profile, rules=None) -> dict:
    rule_set = enrichment.readiness_rules() if rules is None else rules
    physical = getattr(profile, 'physical', None) or {}
    blockers, warnings = [], []
    for rule in rule_set.get('physical', []):
        if not _triggered(rule, physical):
            continue
        hits = _match_majors(rule, group.majors)
        if not hits:
            continue
        entry = {
            'level': rule.get('level', 'red'), 'label': rule.get('label', rule['condition']),
            'condition': rule['condition'], 'majors': hits,
            'text': f"该专业组包含 {'、'.join(hits)}，与《体检指导意见》相关条款有关",
            'source': rule.get('source'), 'source_url': rule.get('source_url'),
        }
        (blockers if entry['level'] == 'red' else warnings).append(entry)
    intents = set(getattr(profile, 'intent_types', None) or [])
    todos = [dict(item, selected=(item['type'] in intents)) for item in rule_set.get('timeline', [])]
    return {
        'blockers': blockers, 'warnings': warnings, 'todos': todos,
        'version': rule_set.get('version'), 'disclaimer': DISCLAIMER,
        'note': rule_set.get('notes', {}).get('disclaimer'),
    }
