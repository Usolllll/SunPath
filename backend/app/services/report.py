"""运营看板 / 梯度分布 / 运营报表（M9-01 / M9-03 / M9-05）。

全部为只读聚合，仅管理员可见（鉴权由 ``app.core.security.require_admin`` 负责）：
- ``behavior``：按天统计审计日志里的关键行为（注册/建方案/提交/投档结果查询/收藏），日期补零；
- ``tier_distribution``：遍历已保存方案的 ``items[].risk`` 统计冲稳保分布（忽略非法值）；
- ``report`` / ``report_csv``：汇总用户、方案、收藏、消息、梯度、行为与数据质量，
  CSV 导出使用 ``safe_cell`` 防公式注入并带 UTF-8 BOM。

时区口径：库内 ``created_at`` 为 UTC，因此"今天"与按天分桶均使用 UTC 日期。
"""
import csv
import io
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select

from app.models.entities import AuditLog, Favorite, Message, Plan, User
from app.services import quality as quality_service
from app.utils.export import safe_cell

# 审计 action → 看板字段名（以实际存在的 action 为准，缺失即为 0）
BEHAVIOR_ACTIONS = {
    'auth.register': 'register',
    'plan.create': 'plan_create',
    'plan.submit': 'plan_submit',
    'result.query': 'result_query',
    'favorite.add': 'favorite_add',
}
BEHAVIOR_KEYS = tuple(BEHAVIOR_ACTIONS.values())
BEHAVIOR_LABELS = {
    'register': '注册',
    'plan_create': '创建方案',
    'plan_submit': '提交方案',
    'result_query': '查询投档结果',
    'favorite_add': '收藏院校',
}
RISK_KEYS = ('reach', 'steady', 'safe')
RISK_LABELS = {'reach': '冲', 'steady': '稳', 'safe': '保'}
REPORT_NOTE = '运营报表聚合自审计日志与业务表；模拟数据仅用于演示，不代表真实运营指标。'
BEHAVIOR_NOTE = '统计来自审计日志，仅管理员可见'
TIER_NOTE = '按已保存方案的梯度标记统计'
MIN_DAYS, MAX_DAYS = 7, 90


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _clamp_days(days: int) -> int:
    return max(MIN_DAYS, min(MAX_DAYS, int(days)))


def _period(days: int, today: date | None = None) -> tuple[date, datetime]:
    """返回 (周期起始日, 起始时刻)，周期按"截至今天（含）"共 days 天。"""
    today = today or _today()
    start = today - timedelta(days=_clamp_days(days) - 1)
    return start, datetime.combine(start, time.min)


def _count(db, model, *conditions) -> int:
    statement = select(func.count()).select_from(model)
    for condition in conditions:
        statement = statement.where(condition)
    return int(db.scalar(statement) or 0)


def behavior(db, days: int = 30, today: date | None = None) -> dict:
    """按天行为序列（UTC 日期升序、补零）与周期合计。"""
    days = _clamp_days(days)
    start, start_dt = _period(days, today)
    rows = db.execute(
        select(AuditLog.action, AuditLog.created_at)
        .where(AuditLog.action.in_(tuple(BEHAVIOR_ACTIONS)), AuditLog.created_at >= start_dt)
    ).all()
    buckets = {start + timedelta(days=offset): {key: 0 for key in BEHAVIOR_KEYS}
               for offset in range(days)}
    for action, created_at in rows:
        key = BEHAVIOR_ACTIONS.get(action)
        if not key or created_at is None:
            continue
        day = created_at.date()
        if day in buckets:
            buckets[day][key] += 1
    series = [{'date': day.isoformat(), **counts} for day, counts in sorted(buckets.items())]
    totals = {key: sum(item[key] for item in series) for key in BEHAVIOR_KEYS}
    return {'days': days, 'series': series, 'totals': totals, 'note': BEHAVIOR_NOTE}


def tier_distribution(db) -> dict:
    """已保存方案的冲稳保梯度分布（按批次分组，非法 risk 忽略）。"""
    plans = db.scalars(select(Plan)).all()
    tiers = {key: 0 for key in RISK_KEYS}
    by_batch: dict[str, dict] = {}
    for plan in plans:
        batch = plan.batch or '本科批'
        counts = by_batch.setdefault(batch, {key: 0 for key in RISK_KEYS})
        for item in plan.items or []:
            risk = item.get('risk') if isinstance(item, dict) else None
            if risk in tiers:
                tiers[risk] += 1
                counts[risk] += 1
    ordered = [batch for batch in ('本科批', '专科批') if batch in by_batch]
    ordered += sorted(batch for batch in by_batch if batch not in ('本科批', '专科批'))
    return {
        'total_plans': len(plans),
        'tiers': tiers,
        'by_batch': [{'batch': batch, **by_batch[batch]} for batch in ordered],
        'note': TIER_NOTE,
    }


def _quality_summary(db) -> dict:
    """复用数据质量看板，只保留报表需要的摘要字段（避免响应过大）。"""
    dashboard = quality_service.dashboard(db)
    patrol = dashboard.get('patrol') or {}
    return {
        'simulated': dashboard.get('simulated') or {},
        'real_total_rows': (dashboard.get('real') or {}).get('total_rows', 0),
        'versions': len(dashboard.get('versions') or []),
        'patrol_last_checked_at': patrol.get('last_checked_at'),
        'disclaimer': dashboard.get('disclaimer'),
    }


def report(db, days: int = 30, today: date | None = None) -> dict:
    """运营报表：用户/方案/收藏/消息/梯度/行为/数据质量汇总。"""
    days = _clamp_days(days)
    _start, start_dt = _period(days, today)
    behavior_data = behavior(db, days, today)
    tiers = tier_distribution(db)['tiers']
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'period_days': days,
        'users': {
            'total': _count(db, User),
            'new_in_period': _count(db, User, User.created_at >= start_dt),
        },
        'plans': {
            'total': _count(db, Plan),
            'submitted': _count(db, Plan, Plan.status == 'submitted'),
            'new_in_period': _count(db, Plan, Plan.created_at >= start_dt),
        },
        'favorites': {'total': _count(db, Favorite)},
        'messages': {
            'total': _count(db, Message),
            'unread': _count(db, Message, Message.read_at.is_(None)),
        },
        'tiers': tiers,
        'behavior_totals': behavior_data['totals'],
        'quality': _quality_summary(db),
        'note': REPORT_NOTE,
    }


def _cell(value) -> str:
    return safe_cell('' if value is None else value)


def report_csv(result: dict) -> str:
    """报表 CSV（UTF-8 BOM；所有单元格经 safe_cell 防公式注入）。"""
    users, plans = result.get('users') or {}, result.get('plans') or {}
    favorites, messages = result.get('favorites') or {}, result.get('messages') or {}
    tiers = result.get('tiers') or {}
    behavior_totals = result.get('behavior_totals') or {}
    quality = result.get('quality') or {}
    rows = [
        ['指标', '数值'],
        ['报表生成时间', result.get('generated_at')],
        ['统计周期（天）', result.get('period_days')],
        [],
        ['用户', ''],
        ['用户总数', users.get('total')],
        ['周期内新增用户', users.get('new_in_period')],
        ['方案', ''],
        ['方案总数', plans.get('total')],
        ['已提交方案', plans.get('submitted')],
        ['周期内新增方案', plans.get('new_in_period')],
        ['收藏', ''],
        ['收藏总数', favorites.get('total')],
        ['消息', ''],
        ['消息总数', messages.get('total')],
        ['未读消息', messages.get('unread')],
        ['梯度分布', ''],
        *[[f'{RISK_LABELS[key]}（{key}）', tiers.get(key)] for key in RISK_KEYS],
        ['行为合计', ''],
        *[[BEHAVIOR_LABELS[key], behavior_totals.get(key)] for key in BEHAVIOR_KEYS],
        ['数据质量', ''],
        ['真实投档数据总行数', quality.get('real_total_rows')],
        ['当前数据版本数', quality.get('versions')],
        ['最近巡检时间', quality.get('patrol_last_checked_at')],
        ['说明', result.get('note')],
    ]
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    for row in rows:
        writer.writerow([_cell(value) for value in row])
    return '\ufeff' + output.getvalue()


def report_filename() -> str:
    return f'sunpath-report-{datetime.now():%Y%m%d}.csv'
