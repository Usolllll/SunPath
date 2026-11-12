"""批次与填报时间配置（FR-M10-01）。

边界：
- 默认两个批次：本科批（sort 1）/ 专科批（sort 2），由迁移或 ``ensure_defaults`` 幂等补齐；
- 管理员只能更新已存在批次（PUT 不新增、不删除批次）；非法值统一抛 ``BatchValidationError``（API 转 400）；
- ``save_batches`` 只 flush 不 commit，审计与提交由 API 层统一处理，保证“改配置 + 写审计”同一事务。
"""
import re
from datetime import date, timezone

from sqlalchemy import select

from app.models.entities import BatchConfig

DEFAULT_BATCHES = (('本科批', 1), ('专科批', 2))
NOTE = '批次与填报时间以省考试院公告为准'
MAX_NOTE = 200
MAX_NAME = 20
DATE_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}')
# 计算“实际变更项”时忽略 updated_at（它随写入自动变化）
CHANGE_FIELDS = ('active', 'sort_order', 'fill_start', 'fill_end', 'note')


class BatchValidationError(ValueError):
    """批次配置校验失败（API 层转 400）。"""


def _iso_utc(value):
    """SQLite 读回的 datetime 不带时区；统一按 UTC 输出，与方案/消息接口一致。"""
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


def serialize_batch(row) -> dict:
    return {
        'name': row.name,
        'active': bool(row.active),
        'sort_order': int(row.sort_order or 0),
        'fill_start': row.fill_start,
        'fill_end': row.fill_end,
        'note': row.note,
        'updated_at': _iso_utc(row.updated_at),
    }


def list_batches(db, active_only: bool = False) -> list[dict]:
    statement = select(BatchConfig)
    if active_only:
        statement = statement.where(BatchConfig.active.is_(True))
    rows = db.scalars(statement.order_by(BatchConfig.sort_order, BatchConfig.name)).all()
    return [serialize_batch(row) for row in rows]


def snapshot(db) -> dict:
    """当前配置快照 {name: {...}}，供 API 计算实际变更的批次名。"""
    return {row.name: serialize_batch(row) for row in db.scalars(select(BatchConfig)).all()}


def changed_names(before: dict, after_items: list[dict]) -> list[str]:
    changed = []
    for item in after_items:
        old = before.get(item['name'])
        if old is None or any(old.get(field) != item.get(field) for field in CHANGE_FIELDS):
            changed.append(item['name'])
    return changed


def _clean_date(value, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise BatchValidationError(f'{label}必须是 YYYY-MM-DD 文本')
    text = value.strip()
    if not text:
        return None
    if not DATE_PATTERN.fullmatch(text):
        raise BatchValidationError(f'{label}格式应为 YYYY-MM-DD：{value}')
    try:
        date.fromisoformat(text)
    except ValueError:
        raise BatchValidationError(f'{label}不是有效日期：{value}') from None
    return text


def _clean_note(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise BatchValidationError('备注必须是文本')
    text = value.strip()
    return text[:MAX_NOTE] if text else None


def save_batches(db, payload) -> list[dict]:
    """更新已有批次配置。

    ``payload`` 形如 ``{'batches': [{'name': ..., 'active': ..., ...}]}``（也接受裸列表）。
    先整体校验再写入，避免部分生效；成功返回更新后的列表（已 flush，未 commit）。
    """
    items = payload.get('batches') if isinstance(payload, dict) else payload
    if not isinstance(items, list) or not items:
        raise BatchValidationError('batches 必须是非空数组')
    rows = {row.name: row for row in db.scalars(select(BatchConfig)).all()}
    normalized = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise BatchValidationError('每个批次配置必须是对象')
        name = item.get('name')
        if not isinstance(name, str) or not name.strip():
            raise BatchValidationError('批次名称不能为空')
        name = name.strip()
        if len(name) > MAX_NAME:
            raise BatchValidationError(f'批次名称最长 {MAX_NAME} 个字符')
        if name not in rows:
            raise BatchValidationError(f'未知批次：{name}（只允许更新已配置批次）')
        if name in seen:
            raise BatchValidationError(f'批次重复：{name}')
        seen.add(name)
        row = rows[name]
        active = item.get('active', row.active)
        if not isinstance(active, bool):
            raise BatchValidationError(f'{name} 的 active 必须是布尔值')
        sort_order = item.get('sort_order', row.sort_order)
        if isinstance(sort_order, bool) or not isinstance(sort_order, int):
            raise BatchValidationError(f'{name} 的 sort_order 必须是整数')
        fill_start = _clean_date(item.get('fill_start'), f'{name} 填报开始日期')
        fill_end = _clean_date(item.get('fill_end'), f'{name} 填报结束日期')
        if fill_start and fill_end and fill_start > fill_end:
            raise BatchValidationError(f'{name} 的填报开始日期不能晚于结束日期')
        note = _clean_note(item.get('note'))
        normalized.append((row, active, sort_order, fill_start, fill_end, note))

    for row, active, sort_order, fill_start, fill_end, note in normalized:
        row.active = active
        row.sort_order = sort_order
        row.fill_start = fill_start
        row.fill_end = fill_end
        row.note = note
    db.flush()
    for row in rows.values():
        db.refresh(row)
    return list_batches(db)


def ensure_defaults(db) -> int:
    """补齐默认两个批次（幂等）；返回新增行数。调用方负责 commit。"""
    existing = set(db.scalars(select(BatchConfig.name)).all())
    created = 0
    for name, sort_order in DEFAULT_BATCHES:
        if name in existing:
            continue
        db.add(BatchConfig(name=name, active=True, sort_order=sort_order))
        created += 1
    if created:
        db.flush()
    return created
