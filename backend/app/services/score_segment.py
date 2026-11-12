"""一分一段表查询服务（M4-02）。

数据来自 ``app/data/score_segments.json``（示例数据，进程内 lru_cache 缓存）。
一分一段只用于「位次参考」：累计人数给出考生分数之上的大致人数区间，
不代表任何录取结果。

口径：
- ``cumulative`` 为该分数及以上的累计人数（分数降序表，数值严格递增）；
- ``rank_estimate`` 取 ``cumulative``，即「该分数段以上人数」的位次参考；
- ``percentile`` = cumulative / 该省高考人数（数据文件里的 ``total_candidates``；
  缺失时回退为该省一分一段表的最大累计人数），四舍五入 2 位小数。

省份/年份未收录返回 ``None``，由 API 层翻译成 404；分数不在已收录区间也返回 ``None``。
"""
import json
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parents[1] / 'data' / 'score_segments.json'
PROVINCE_KEY = 'provinces'


@lru_cache(maxsize=1)
def load_data() -> dict:
    """读取一分一段数据（只读文件；文件缺失或损坏时返回空结构而不是 500）。"""
    try:
        payload = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {'_meta': {}, PROVINCE_KEY: {}}
    if not isinstance(payload, dict) or not isinstance(payload.get(PROVINCE_KEY), dict):
        return {'_meta': {}, PROVINCE_KEY: {}}
    return payload


def meta() -> dict:
    """数据文件的 _meta（data_mode / note / updated_at 等）。"""
    meta_block = load_data().get('_meta')
    return meta_block if isinstance(meta_block, dict) else {}


def dataset(province: str, year: int | str) -> dict | None:
    """取某省某年的一分一段数据集；未收录返回 None。"""
    province_block = load_data().get(PROVINCE_KEY, {}).get(str(province))
    if not isinstance(province_block, dict):
        return None
    entry = province_block.get(str(year))
    return entry if isinstance(entry, dict) else None


def _total_candidates(entry: dict) -> int:
    """该省高考人数：优先用数据里的 total_candidates，缺失时回退为表内最大累计人数。"""
    total = entry.get('total_candidates')
    if isinstance(total, int) and total > 0:
        return total
    cumulative_values = []
    for segment in entry.get('segments') or []:
        try:
            cumulative_values.append(int(segment.get('cumulative')))
        except (TypeError, ValueError):
            continue
    return max(cumulative_values, default=0)


def _segments_of(entry: dict) -> list[dict]:
    """规范化分段列表：按分数降序；丢弃字段缺失/非整数的脏行。"""
    cleaned = []
    for segment in entry.get('segments') or []:
        try:
            cleaned.append({
                'score': int(segment['score']),
                'count': int(segment['count']),
                'cumulative': int(segment['cumulative']),
            })
        except (KeyError, TypeError, ValueError):
            continue
    cleaned.sort(key=lambda item: item['score'], reverse=True)
    return cleaned


def _provenance(province: str, year: int | str, entry: dict) -> dict:
    meta_block = meta()
    return {
        'province': str(province),
        'exam_year': int(year),
        'subject_type': entry.get('subject_type'),
        'total_candidates': _total_candidates(entry),
        'source_url': entry.get('source_url'),
        'published_at': entry.get('published_at'),
        'data_mode': meta_block.get('data_mode', '未知'),
        'note': meta_block.get('note', ''),
    }


def query(province: str, year: int | str, score: int) -> dict | None:
    """按省份/年份/分数查询一分一段信息；未收录或区间外返回 None。"""
    entry = dataset(province, year)
    if entry is None:
        return None
    try:
        wanted = int(score)
    except (TypeError, ValueError):
        return None
    match = next((item for item in _segments_of(entry) if item['score'] == wanted), None)
    if match is None:
        return None
    total = _total_candidates(entry)
    percentile = round(match['cumulative'] / total, 2) if total else None
    result = _provenance(province, year, entry)
    result.update({
        'score': match['score'],
        'count': match['count'],
        'cumulative': match['cumulative'],
        'rank_estimate': match['cumulative'],
        'percentile': percentile,
    })
    return result


def segments(province: str, year: int | str, limit: int = 60) -> dict | None:
    """返回该省该年一分一段分段列表（分数降序，最多 limit 条）+ 数据口径。"""
    entry = dataset(province, year)
    if entry is None:
        return None
    try:
        size = max(0, int(limit))
    except (TypeError, ValueError):
        size = 60
    rows = _segments_of(entry)[:size]
    result = _provenance(province, year, entry)
    result.update({
        'direction': 'desc',
        'total': len(rows),
        'segments': rows,
    })
    return result
