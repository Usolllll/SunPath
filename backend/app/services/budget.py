"""家庭预算：四年总成本估算（学费+住宿费+生活费），全部可追溯到字段或标注为估算。"""
from app.services import enrichment

BUDGET_TIERS = [
    (80000, '经济型', '≤ 8 万'),
    (120000, '常规型', '8–12 万'),
    (200000, '宽裕型', '12–20 万'),
    (350000, '高投入型', '20–35 万'),
]
BUDGET_TIER_TOP = '自定'
DEFAULT_SUPPORT_NOTE = '生活费按城市等级估算（国家统计局消费支出口径 × 在校生系数），非官方数据'


def living_cost(item: dict) -> int:
    university = item.get('university') or {}
    return enrichment.annual_living_cost(university.get('city_tier'))


def four_year_cost(item: dict) -> dict:
    years = item.get('duration_years') or 4
    tuition = item.get('tuition') or 0
    accommodation = item.get('accommodation') or 0
    living = living_cost(item)
    total = (tuition + accommodation) * years + living * years
    return {
        'tuition': tuition, 'accommodation': accommodation, 'living': living,
        'years': years, 'annual': tuition + accommodation + living, 'total': total,
        'note': DEFAULT_SUPPORT_NOTE,
    }


def budget_tier(total: int | None) -> str:
    if total is None:
        return '未知'
    for ceiling, name, _label in BUDGET_TIERS:
        if total <= ceiling:
            return name
    return BUDGET_TIER_TOP


def budget_summary(items: list[dict], budget_total: int | None = None) -> dict:
    totals = [item['cost']['total'] for item in items if item.get('cost')]
    if not totals:
        return {'count': 0, 'total': 0, 'min': 0, 'max': 0, 'over_budget': 0, 'budget': budget_total}
    return {
        'count': len(totals),
        'total': sum(totals),
        'min': min(totals),
        'max': max(totals),
        'over_budget': sum(1 for t in totals if budget_total and t > budget_total),
        'budget': budget_total,
        'usage': round(sum(totals) / budget_total, 3) if budget_total else None,
    }
