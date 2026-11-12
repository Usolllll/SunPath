"""政策公告索引 + 站内消息生成（FR-M8-01 / M8-02 / M8-03 / M8-05）。

边界：
- 公告/资讯只做索引与摘要，逐条带官方来源（app/data/announcements.json），不编造内容；
- 消息只存本人消息，按订阅生成提醒，用 ``dedupe_key`` 保证 refresh 幂等；
- refresh 只“提醒”不构成填报建议：征集时间以省考试院公告为准。

``refresh`` 支持注入 ``today`` / ``schedule``，既方便单测，也避免把时间窗逻辑写死在接口层。
"""
import hashlib
import json
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func, or_, select, update

from app.models.entities import Message, Plan
from app.services import quality

DATA_DIR = Path(__file__).resolve().parents[1] / 'data'
DEFAULT_SUBSCRIPTION = {'types': ['collection', 'plan'], 'channel': 'site', 'lead_days': 3}
SUBSCRIPTION_TYPES = ('collection', 'policy', 'lecture', 'quality', 'plan', 'result')
CHANNELS = ('site',)
MESSAGE_LIMIT = 50
MAX_TITLE = 120
MAX_BODY = 500
MAX_LINK = 200
MAX_DEDUPE = 120


def _load(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding='utf-8'))


@lru_cache
def announcements() -> list[dict]:
    return list(_load('announcements.json').get('items') or [])


@lru_cache
def admission_schedule() -> dict:
    return _load('admission_schedule.json')


def iso_utc(value):
    """SQLite 读回的 datetime 不带时区；统一按 UTC 输出。"""
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


# ---------------------------------------------------------------- 公告/资讯
def notice_brief(item: dict) -> dict:
    return {
        'id': item.get('id'), 'category': item.get('category'), 'title': item.get('title'),
        'publish_date': item.get('publish_date'), 'source': item.get('source'),
        'source_url': item.get('source_url') or '', 'summary': item.get('summary'),
        'tags': list(item.get('tags') or []),
    }


def _matched(item: dict, keyword: str) -> bool:
    haystack = ' '.join([
        str(item.get('title') or ''), str(item.get('summary') or ''),
        str(item.get('source') or ''), ' '.join(str(tag) for tag in item.get('tags') or []),
    ]).lower()
    return keyword in haystack


def list_notices(category: str = '', q: str = '', limit: int = 50) -> dict:
    """按分类/关键词过滤；分类 chips 始终返回全量分类，便于前端稳定展示。"""
    everything = announcements()
    items = [item for item in everything if not category or item.get('category') == category]
    keyword = (q or '').strip().lower()
    if keyword:
        items = [item for item in items if _matched(item, keyword)]
    items = sorted(items, key=lambda item: (str(item.get('publish_date') or ''), str(item.get('id') or '')),
                   reverse=True)
    limit = max(1, min(int(limit or MESSAGE_LIMIT), 50))
    categories = sorted({item.get('category') for item in everything if item.get('category')})
    return {'total': len(items), 'categories': categories, 'items': [notice_brief(item) for item in items[:limit]]}


def find_notice(notice_id: str) -> dict | None:
    target = str(notice_id)
    return next((item for item in announcements() if str(item.get('id')) == target), None)


def _latest_notice() -> dict | None:
    items = announcements()
    if not items:
        return None
    return max(items, key=lambda item: (str(item.get('publish_date') or ''), str(item.get('id') or '')))


# ---------------------------------------------------------------- 订阅偏好
def normalize_subscription(stored) -> dict:
    """把库里的订阅值归一为 {types, channel, lead_days}；缺失/非法项回退默认值。"""
    if not isinstance(stored, dict):
        return {'types': list(DEFAULT_SUBSCRIPTION['types']), 'channel': 'site',
                'lead_days': DEFAULT_SUBSCRIPTION['lead_days']}
    raw_types = stored.get('types')
    if isinstance(raw_types, list):
        types = [item for item in dict.fromkeys(raw_types) if item in SUBSCRIPTION_TYPES]
    else:
        types = list(DEFAULT_SUBSCRIPTION['types'])
    channel = stored.get('channel') if stored.get('channel') in CHANNELS else 'site'
    lead_days = stored.get('lead_days')
    if isinstance(lead_days, bool) or not isinstance(lead_days, int) or not 0 <= lead_days <= 14:
        lead_days = DEFAULT_SUBSCRIPTION['lead_days']
    return {'types': types, 'channel': channel, 'lead_days': lead_days}


def current_subscription(user) -> dict:
    profile = getattr(user, 'profile', None)
    return normalize_subscription(getattr(profile, 'subscription', None))


# ---------------------------------------------------------------- 消息读写
def serialize_message(message: Message) -> dict:
    return {
        'id': message.id, 'type': message.type, 'title': message.title, 'body': message.body,
        'link': message.link, 'created_at': iso_utc(message.created_at), 'read_at': iso_utc(message.read_at),
    }


def unread_count(db, user) -> int:
    return int(db.scalar(select(func.count()).select_from(Message)
                         .where(Message.user_id == user.id, Message.read_at.is_(None))) or 0)


def list_messages(db, user, only_unread: bool = False) -> dict:
    statement = select(Message).where(Message.user_id == user.id)
    if only_unread:
        statement = statement.where(Message.read_at.is_(None))
    rows = db.scalars(statement.order_by(Message.created_at.desc(), Message.id.desc()).limit(MESSAGE_LIMIT)).all()
    return {'unread': unread_count(db, user), 'items': [serialize_message(row) for row in rows]}


def create_message(db, user, *, type: str, title: str, body: str, link: str | None = None,
                   dedupe_key: str | None = None) -> bool:
    """写一条本人消息；dedupe_key 已存在时跳过并返回 False（幂等）。"""
    if dedupe_key:
        existing = db.scalar(select(Message.id).where(Message.user_id == user.id,
                                                      Message.dedupe_key == dedupe_key))
        if existing:
            return False
    db.add(Message(
        user_id=user.id, type=str(type)[:30], title=str(title)[:MAX_TITLE], body=str(body)[:MAX_BODY],
        link=(str(link)[:MAX_LINK] if link else None),
        dedupe_key=(str(dedupe_key)[:MAX_DEDUPE] if dedupe_key else None),
    ))
    db.flush()
    return True


def get_owned_message(db, user, message_id: int) -> Message | None:
    return db.scalar(select(Message).where(Message.id == message_id, Message.user_id == user.id))


def mark_read(db, message: Message) -> None:
    if message.read_at is None:
        message.read_at = datetime.now(timezone.utc)


def mark_all_read(db, user) -> int:
    result = db.execute(update(Message).where(Message.user_id == user.id, Message.read_at.is_(None))
                        .values(read_at=datetime.now(timezone.utc)))
    return int(result.rowcount or 0)


# ---------------------------------------------------------------- 订阅提醒（refresh）
def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _collection_candidates(user, lead_days: int, today: date, schedule) -> list[dict]:
    """征集志愿时间窗：进行中，或距开始 ≤ lead_days 天。"""
    profile = getattr(user, 'profile', None)
    province = getattr(profile, 'province', None)
    data = admission_schedule() if schedule is None else schedule
    batches = (data.get('provinces') or {}).get(province) or data.get('default') or []
    results = []
    for batch in batches:
        batch_name = batch.get('batch') or '本科批'
        for event in batch.get('events') or []:
            if event.get('stage') != '征集志愿':
                continue
            start, end = _parse_date(event.get('start')), _parse_date(event.get('end'))
            if not start or not end:
                continue
            ongoing = start <= today <= end
            days = (start - today).days
            upcoming = today < start and days <= lead_days
            if not (ongoing or upcoming):
                continue
            when = '正在进行中' if ongoing else f'距开始还有 {days} 天'
            results.append({
                'type': 'collection',
                'title': f'{batch_name}征集志愿提醒',
                'body': (f'{province or "本省"}{batch_name}征集志愿时间 {start.isoformat()} 至 '
                         f'{end.isoformat()}，{when}。请在省教育考试院规定时间内填报，并核对缺额计划与资格要求；'
                         f'具体以官方公告为准。'),
                'link': '/notices',
                'dedupe_key': f"collection:{province or 'default'}:{batch_name}:{start.isoformat()}",
            })
    return results


def _plan_candidates(db, user) -> list[dict]:
    """已保存但未提交（草稿）的方案提醒；按草稿集合去重，避免反复打扰。"""
    drafts = db.scalars(
        select(Plan).where(Plan.user_id == user.id, or_(Plan.status.is_(None), Plan.status == 'draft'))
        .order_by(Plan.updated_at.desc())
    ).all()
    if not drafts:
        return []
    ids = sorted(plan.id for plan in drafts)
    digest = hashlib.sha1(','.join(str(plan_id) for plan_id in ids).encode()).hexdigest()[:16]
    names = [plan.name for plan in drafts]
    shown = '、'.join(f'「{name}」' for name in names[:3])
    more = f' 等 {len(names)} 份' if len(names) > 3 else ''
    return [{
        'type': 'plan',
        'title': f'你有 {len(drafts)} 份志愿方案尚未提交',
        'body': (f'{shown}{more}方案仍是草稿。确认冲稳保梯度与专业组后，可在「志愿规划」页提交；'
                 f'提交后不可编辑，如需修改请先撤回。'),
        'link': '/planner',
        'dedupe_key': f'plan:drafts:{digest}',
    }]


def _policy_candidates() -> list[dict]:
    """最新一条政策/资讯摘要；按公告 id 去重（有新公告才再提醒）。"""
    latest = _latest_notice()
    if not latest:
        return []
    return [{
        'type': 'policy',
        'title': f"政策公告：{latest.get('title') or latest.get('id')}",
        'body': (f"{latest.get('summary') or ''}（来源：{latest.get('source') or '官方'}；"
                 f"发布日期 {latest.get('publish_date') or '未标注'}）"),
        'link': latest.get('source_url') or '/notices',
        'dedupe_key': f"policy:{latest.get('id')}",
    }]


def _quality_candidates() -> list[dict]:
    """巡检最新报告存在 changed 源时提醒；按报告文件去重。"""
    report = quality.latest_patrol()
    if not report:
        return []
    changed = [item for item in report.get('items') or [] if item.get('changed') is True]
    if not changed:
        return []
    markers = '、'.join(str(item.get('id')) for item in changed[:5])
    marker = report.get('report_file') or report.get('last_checked_at') or 'latest'
    return [{
        'type': 'quality',
        'title': '官方数据源有新变化，待复核',
        'body': (f'最新巡检发现 {len(changed)} 个数据源内容有变化（{markers}），已登记待复核。'
                 f'请以省考试院/高校官方最新公告为准，本提醒不构成录取预测。'),
        'link': '/quality',
        'dedupe_key': f'quality:patrol:{marker}',
    }]


def refresh(db, user, today: date | None = None, schedule: dict | None = None) -> dict:
    """按订阅生成提醒消息；dedupe_key 保证重复 refresh 不重复发送。"""
    subscription = current_subscription(user)
    types = set(subscription['types'])
    today = today or date.today()
    candidates = []
    if 'collection' in types:
        candidates += _collection_candidates(user, subscription['lead_days'], today, schedule)
    if 'plan' in types:
        candidates += _plan_candidates(db, user)
    if 'policy' in types:
        candidates += _policy_candidates()
    if 'quality' in types:
        candidates += _quality_candidates()
    created = skipped = 0
    for candidate in candidates:
        if create_message(db, user, **candidate):
            created += 1
        else:
            skipped += 1
    return {'created': created, 'skipped': skipped}
