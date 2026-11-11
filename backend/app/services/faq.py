"""FAQ 知识库检索（FR-M8-04）。

数据来自 ``app/data/faq.json``（只读、随代码发布）；答案均为项目自撰摘要，
政策类条目附官方来源。查询按 question / keywords / answer 做子串匹配，
多个关键词用空格分隔时要求全部命中。
"""
import json
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parents[1] / 'data' / 'faq.json'
FIELDS = ('id', 'category', 'question', 'answer', 'source', 'source_url')


@lru_cache(maxsize=1)
def load_items() -> tuple[dict, ...]:
    """读取 FAQ 条目（进程内缓存；文件缺失时返回空元组而不是 500）。"""
    try:
        payload = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return ()
    items = payload.get('items') or []
    return tuple(item for item in items if isinstance(item, dict) and item.get('id'))


def categories() -> list[str]:
    """按原始顺序返回分类（去重）。"""
    result: list[str] = []
    for item in load_items():
        category = item.get('category')
        if category and category not in result:
            result.append(category)
    return result


def serialize(item: dict) -> dict:
    return {field: item.get(field) for field in FIELDS}


def _haystack(item: dict) -> str:
    keywords = item.get('keywords') or []
    return ' '.join([str(item.get('question') or ''), ' '.join(map(str, keywords)),
                     str(item.get('answer') or '')]).casefold()


def search(query: str = '', category: str | None = None) -> dict:
    """模糊检索 FAQ；``query`` 为空表示全部，``category`` 为空表示全部分类。"""
    tokens = [token for token in (query or '').strip().casefold().split() if token]
    wanted = (category or '').strip()
    matched = []
    for item in load_items():
        if wanted and item.get('category') != wanted:
            continue
        if tokens:
            text = _haystack(item)
            if not all(token in text for token in tokens):
                continue
        matched.append(serialize(item))
    return {'total': len(matched), 'categories': categories(), 'items': matched}
