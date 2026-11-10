"""取舍沙盘打分（v2）：S 院校分量 / M 专业分量 / F 位次适配 + 转专业软加分。

约束：打分只影响"同一梯度内"的候选选择与顺序；候选池与冲稳保配额仍由
recommender.recommend / balanced_plan 决定，本模块不改变任何硬约束。
"""
from app.services import enrichment

MODE_WEIGHTS = {
    'school': (0.60, 0.15, 0.25),
    'balanced': (0.40, 0.40, 0.20),
    'major': (0.15, 0.60, 0.25),
}
MODE_LABELS = {'school': '偏学校', 'balanced': '均衡', 'major': '偏专业'}
DEFAULT_MODE = 'balanced'
CITY_SCORES = {1: 100, 2: 80, 3: 60, 4: 40}
DEFAULT_CITY_SCORE = 50
DEFAULT_LEVEL_SCORE = 40

# 院校类型 × 专业门类的粗契合度（启发式，仅用于排序，不作为事实）
CATEGORY_FIT = {
    '理工类': {'工学': 90, '理学': 85, '交叉学科': 85, '医学': 60, '经济学': 55, '管理学': 50},
    '综合类': {'工学': 80, '理学': 85, '医学': 75, '经济学': 80, '管理学': 78, '文学': 78, '法学': 75, '历史学': 70, '哲学': 65, '教育学': 65, '农学': 70, '艺术学': 65, '交叉学科': 75},
    '师范类': {'教育学': 95, '文学': 85, '理学': 82, '历史学': 78, '艺术学': 75},
    '财经类': {'经济学': 95, '管理学': 92, '法学': 70, '文学': 60},
    '医药类': {'医学': 98, '理学': 75},
    '农林类': {'农学': 95, '理学': 78, '工学': 65},
    '语言类': {'文学': 95, '法学': 70},
    '政法类': {'法学': 95, '管理学': 70},
    '艺术类': {'艺术学': 98, '文学': 60},
    '民族类': {'文学': 70, '法学': 68, '管理学': 65},
}
DEFAULT_CATEGORY_FIT = 60


def normalize_mode(mode: str | None) -> str:
    return mode if mode in MODE_WEIGHTS else DEFAULT_MODE


def weights(mode: str | None) -> dict:
    ws, wm, wf = MODE_WEIGHTS[normalize_mode(mode)]
    return {'school': ws, 'major': wm, 'fit': wf}


def school_score(item: dict) -> float:
    university = item.get('university') or {}
    level = university.get('level_tier')
    level_value = DEFAULT_LEVEL_SCORE if level is None else level
    city = university.get('city_tier')
    city_value = CITY_SCORES.get(city, DEFAULT_CITY_SCORE)
    return round(0.7 * level_value + 0.3 * city_value, 2)


def interest_match(majors: list, interests: dict | None) -> float | None:
    """考生六型兴趣与专业卡 RIASEC 匹配（0-100）；无兴趣或无卡片数据返回 None。"""
    if not interests:
        return None
    cards = enrichment.major_cards()
    best = None
    for name in majors or []:
        card = cards.get(name)
        if not card:
            continue
        main = card.get('riasec_main') or []
        secondary = card.get('riasec_secondary') or []
        numerator = sum(interests.get(t, 0) for t in main) + 0.5 * sum(interests.get(t, 0) for t in secondary)
        denominator = len(main) + 0.5 * len(secondary)
        if not denominator:
            continue
        value = min(100.0, numerator / denominator)
        best = value if best is None else max(best, value)
    return None if best is None else round(best, 2)


def keyword_match(majors: list, keywords: list | None) -> float:
    if not keywords or not majors:
        return 0.0
    hits = 0
    for keyword in keywords:
        if any(keyword in major for major in majors):
            hits += 1
    return round(min(100.0, 100.0 * hits / len(keywords)), 2)


def category_fit(item: dict) -> float:
    university = item.get('university') or {}
    group_category = item.get('major_category')
    if not group_category:
        return float(DEFAULT_CATEGORY_FIT)
    table = CATEGORY_FIT.get(university.get('category') or '', {})
    return float(table.get(group_category, DEFAULT_CATEGORY_FIT))


def major_score(item: dict, profile, interests: dict | None) -> float:
    interest = interest_match(item.get('majors') or [], interests)
    if interest is None:
        # 无兴趣测评：退化为关键词命中；仍无偏好则中性 50
        keywords = getattr(profile, 'majors', None) or []
        interest = keyword_match(item.get('majors') or [], keywords) if keywords else 50.0
    return round(0.6 * interest + 0.4 * category_fit(item), 2)


def rank_fit(item: dict) -> float:
    ratio = item.get('rank_ratio')
    if ratio is None:
        return 0.0
    return round(max(0.0, 1 - abs(ratio - 1.0) / 0.35) * 100, 2)


def transfer_bonus(item: dict) -> float:
    """转专业友好度软加分（0-8），未收录不加分。"""
    friendly = (item.get('university') or {}).get('transfer_friendly')
    if not friendly:
        return 0.0
    return round((friendly - 1) / 2 * 8, 2)


def score_item(item: dict, profile, mode: str | None, interests: dict | None) -> dict:
    school = school_score(item)
    major = major_score(item, profile, interests)
    fit = rank_fit(item)
    ws, wm, wf = MODE_WEIGHTS[normalize_mode(mode)]
    total = round(ws * school + wm * major + wf * fit + transfer_bonus(item), 2)
    return {
        'school_score': school, 'major_score': major, 'rank_fit': fit,
        'transfer_bonus': transfer_bonus(item), 'total_score': total,
        'weights': {'school': ws, 'major': wm, 'fit': wf},
    }


def diff_plans(a_items: list[dict], b_items: list[dict]) -> dict:
    """两套方案的逐位差异（a=基准, b=对照）。"""
    a_ids = [item['id'] for item in a_items]
    b_ids = [item['id'] for item in b_items]
    a_set, b_set = set(a_ids), set(b_ids)
    changed = sum(1 for x, y in zip(a_ids, b_ids) if x != y)
    rank_delta = {str(i): b_ids.index(i) - a_ids.index(i) for i in a_ids if i in b_set}

    def mean(items, key):
        values = [item.get(key) for item in items if item.get(key) is not None]
        return round(sum(values) / len(values), 2) if values else None

    return {
        'a_count': len(a_ids), 'b_count': len(b_ids),
        'changed': changed,
        'added': [i for i in b_ids if i not in a_set],
        'removed': [i for i in a_ids if i not in b_set],
        'rank_delta': rank_delta,
        'metric_delta': {
            'school': round((mean(b_items, 'school_score') or 0) - (mean(a_items, 'school_score') or 0), 2),
            'major': round((mean(b_items, 'major_score') or 0) - (mean(a_items, 'major_score') or 0), 2),
            'rank_fit': round((mean(b_items, 'rank_fit') or 0) - (mean(a_items, 'rank_fit') or 0), 2),
        },
    }


def summarize(diff: dict) -> str:
    school = diff['metric_delta']['school']
    major = diff['metric_delta']['major']

    def direction(value):
        if value >= 0.5:
            return '提升', abs(value)
        if value <= -0.5:
            return '下降', abs(value)
        return '基本持平', 0

    def phrase(name, value):
        word, amount = direction(value)
        return f'{name}{word}' if word == '基本持平' else f'{name}平均{word}{amount:.0f} 分'

    return f"切换后 {diff['changed']} 个志愿变化：{phrase('院校层次', school)}，{phrase('专业对口', major)}"
