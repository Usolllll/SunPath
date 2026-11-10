"""v2 维度映射：把人工维护的 JSON 映射表落到院校/专业组字段（只做换算，不编造事实）。"""
import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / 'data'


def _load(name: str) -> dict:
    path = DATA_DIR / name
    return json.loads(path.read_text(encoding='utf-8'))


@lru_cache
def level_scores() -> dict:
    return _load('level_scores.json')['levels']


@lru_cache
def city_tiers() -> dict:
    return _load('city_tiers.json')['cities']


@lru_cache
def living_costs() -> dict:
    return _load('living_costs.json')


@lru_cache
def major_cards() -> dict:
    data = _load('majors.json')
    return {card['name']: card for card in data['majors']}


@lru_cache
def readiness_rules() -> dict:
    return _load('readiness_rules.json')


def level_tier(level: str | None) -> int | None:
    return level_scores().get(level or '')


def city_tier(city: str | None) -> int | None:
    return city_tiers().get(city or '')


def annual_living_cost(city_tier_value: int | None) -> int:
    costs = living_costs()
    tier_map = costs.get('city_tier_annual', {})
    return int(tier_map.get(str(city_tier_value)) or costs.get('default_annual') or 17000)


def apply_university(university) -> None:
    """写入 v2 院校维度；未收录的城市/层次保持 None，不猜测。"""
    university.level_tier = level_tier(university.level)
    university.city_tier = city_tier(university.city)


def apply_group(group, *, tuition_type: str | None = None, accommodation: int | None = None,
                duration_years: int | None = None, cost_year: int | None = None) -> None:
    group.tuition_type = group.tuition_type or tuition_type or '公办'
    group.accommodation = group.accommodation if group.accommodation is not None else (accommodation or 1000)
    group.duration_years = group.duration_years or duration_years or 4
    group.cost_year = group.cost_year or cost_year or 2026
