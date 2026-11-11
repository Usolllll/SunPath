"""数据字典（FR-M9-02）：把选题/批次/模式/预算/数据源等口径集中暴露给前端与运维。

字典里的层级、城市等级、预算档位与数据源均直接读取仓库内的 JSON 登记表或现有
服务常量，避免前端与后端各写一份枚举导致口径漂移。
"""
import json
from functools import lru_cache
from pathlib import Path

from app.schemas.dto import PROVINCES, SUBJECTS
from app.services import budget, scoring

DATA_DIR = Path(__file__).resolve().parents[1] / 'data'
BATCHES = ['本科批', '专科批']
RISK_LABELS = {'reach': '冲刺', 'steady': '稳妥', 'safe': '保底'}
CITY_TIER_LABELS = {1: '一线', 2: '新一线', 3: '二线', 4: '三线及以下'}


@lru_cache(maxsize=None)
def _read_json(filename: str) -> dict:
    payload = json.loads((DATA_DIR / filename).read_text(encoding='utf-8'))
    return payload if isinstance(payload, dict) else {}


def levels() -> list[str]:
    """院校层次档位（来自 level_scores.json 的 key，内部排序用）。"""
    return list((_read_json('level_scores.json').get('levels') or {}).keys())


def city_tiers() -> list[dict]:
    """城市等级 1–4 及其代表城市（来自 city_tiers.json）。"""
    cities = _read_json('city_tiers.json').get('cities') or {}
    grouped: dict[int, list[str]] = {}
    for city, tier in cities.items():
        try:
            grouped.setdefault(int(tier), []).append(city)
        except (TypeError, ValueError):
            continue
    return [{'tier': tier, 'label': CITY_TIER_LABELS.get(tier, str(tier)),
             'cities': sorted(grouped.get(tier, []))} for tier in sorted(grouped)]


def modes() -> list[dict]:
    """三档取舍模式的排序权重（复用 scoring.MODE_WEIGHTS，口径唯一）。"""
    return [{'key': key, 'label': scoring.MODE_LABELS.get(key, key), 'weights': scoring.weights(key)}
            for key in scoring.MODE_WEIGHTS]


def budget_tiers() -> list[dict]:
    """四年总成本分档（复用 budget.BUDGET_TIERS）。"""
    return [{'name': name, 'range': label} for _ceiling, name, label in budget.BUDGET_TIERS]


def data_sources() -> list[dict]:
    """官方数据源登记表（只暴露 id/数据集/省份/自动化方式，不含抓取细节）。"""
    sources = _read_json('source_registry.json').get('sources') or []
    return [{'id': source.get('id'), 'dataset': source.get('dataset'),
             'province': source.get('province'), 'automation': source.get('automation')}
            for source in sources if isinstance(source, dict)]


def build() -> dict:
    return {
        'provinces': PROVINCES,
        'subjects': SUBJECTS,
        'levels': levels(),
        'city_tiers': city_tiers(),
        'batches': BATCHES,
        'modes': modes(),
        'risks': RISK_LABELS,
        'budget_tiers': budget_tiers(),
        'data_sources': data_sources(),
    }
