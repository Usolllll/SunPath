"""录取进程、模拟投档结果与征集志愿时间窗（FR-M7-01 / M7-02 / M7-03 / M7-05）。

- 录取时间轴来自 ``app/data/admission_schedule.json``（演示样例，按省考试院公告更新）；
- 模拟投档只做"是否达到近一次官方投档最低位次"的演示判定，**不输出概率/百分比**；
- 数据缺失时明确返回 ``no_data``，不做任何推测。
"""
import csv
import io
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.services import real_data
from app.utils.export import safe_cell

SCHEDULE_FILE = Path(__file__).resolve().parents[1] / 'data' / 'admission_schedule.json'
RISK_LABELS = {'reach': '冲', 'steady': '稳', 'safe': '保'}
RESULT_DISCLAIMER = '模拟投档仅按官方投档最低位次演示判定，不代表录取结果或概率。'
NO_OFFICIAL_LABEL = '暂无官方投档数据'
PASS_LABEL = '达到近一次官方投档最低位次'
FAIL_LABEL = '未达到近一次官方投档最低位次'
NO_RANK_LABEL = '暂无你的位次，无法判定'


@lru_cache(maxsize=1)
def load_schedule() -> dict:
    """读取时间轴文件；缺失/损坏时返回空结构，接口仍可降级返回。"""
    try:
        payload = json.loads(SCHEDULE_FILE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {'_meta': {}, 'provinces': {}, 'default': []}
    return payload if isinstance(payload, dict) else {'_meta': {}, 'provinces': {}, 'default': []}


def _as_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _state(event: dict, today: date) -> str:
    """按今天计算 done / active / upcoming（含首尾日期）。"""
    start, end = _as_date(event.get('start')), _as_date(event.get('end'))
    if end and today > end:
        return 'done'
    if start and today < start:
        return 'upcoming'
    return 'active'


def _event(event: dict, today: date) -> dict:
    return {
        'stage': event.get('stage'),
        'start': event.get('start'),
        'end': event.get('end'),
        'status': event.get('status'),
        'state': _state(event, today),
    }


def _batch(batch: dict, today: date) -> dict:
    events = [_event(event, today) for event in batch.get('events') or [] if isinstance(event, dict)]
    active = [event for event in events if event['state'] == 'active']
    done = [event for event in events if event['state'] == 'done']
    upcoming = [event for event in events if event['state'] == 'upcoming']
    if active:
        current_stage = active[-1]['stage']
    elif done:
        current_stage = done[-1]['stage']
    else:
        current_stage = upcoming[0]['stage'] if upcoming else None
    next_window = None
    if upcoming:
        next_window = {'stage': upcoming[0]['stage'], 'start': upcoming[0]['start'],
                       'end': upcoming[0]['end']}
    return {'batch': batch.get('batch'), 'events': events,
            'current_stage': current_stage, 'next_window': next_window}


def schedule(province: str = '浙江', today: date | None = None) -> dict:
    """某省录取批次时间轴；未收录省份回退 default 并在 note/fallback 中标注。"""
    today = today or date.today()
    payload = load_schedule()
    provinces = payload.get('provinces') or {}
    fallback = province not in provinces
    batches_source = (payload.get('default') or []) if fallback else provinces[province]
    meta = payload.get('_meta') or {}
    note = meta.get('note') or '各批次时间以省教育考试院公告为准。'
    if fallback:
        note = f'省份「{province}」的录取时间轴暂未收录，已回退到通用本科批时间轴；' + note
    return {
        'province': province,
        'fallback': fallback,
        'batches': [_batch(batch, today) for batch in batches_source if isinstance(batch, dict)],
        'note': note,
        'updated_at': meta.get('as_of'),
    }


def simulate(db, plan, profile=None) -> dict:
    """模拟投档：逐条对比「我的位次」与官方投档最低位次，只做达到/未达到判定。

    位次优先取当前画像（profile.rank），无画像时回退方案快照；生源省份同理。
    """
    snapshot = plan.profile_snapshot or {}
    rank = getattr(profile, 'rank', None) if profile is not None else None
    if rank is None:
        rank = snapshot.get('rank')
    province = (getattr(profile, 'province', None) if profile is not None else None) or snapshot.get('province')
    items = []
    summary = {'total': 0, 'pass': 0, 'fail': 0, 'no_data': 0}
    for position, raw in enumerate(plan.items or [], 1):
        item = raw if isinstance(raw, dict) else {}
        university = (item.get('university') or {}).get('name')
        official = real_data.school_official(db, university, province) if university and province else None
        if official is None:
            verdict, label = 'no_data', NO_OFFICIAL_LABEL
        elif rank is None or official.get('min_rank') is None:
            verdict, label = 'no_data', NO_RANK_LABEL
        elif rank <= official['min_rank']:
            verdict, label = 'pass', PASS_LABEL
        else:
            verdict, label = 'fail', FAIL_LABEL
        summary['total'] += 1
        summary[verdict] += 1
        items.append({
            'position': position,
            'university': university,
            'group_name': item.get('name'),
            'risk': item.get('risk'),
            'user_rank': rank,
            'official': official,
            'verdict': verdict,
            'label': label,
        })
    return {
        'plan_id': plan.id,
        'plan_name': plan.name,
        'province': province,
        'profile_rank': rank,
        'summary': summary,
        'items': items,
        'disclaimer': RESULT_DISCLAIMER,
    }


def _cell(value) -> str:
    return safe_cell('' if value is None else value)


def result_csv(result: dict) -> str:
    """导出模拟投档结果（UTF-8 BOM；所有单元格经 safe_cell 防公式注入）。"""
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow([_cell(value) for value in
                     ['序号', '院校', '专业组', '梯度', '你的位次', '官方投档最低位次',
                      '年份', '科类', '来源链接', '判定']])
    for item in result.get('items') or []:
        official = item.get('official') or {}
        row = [
            item.get('position'),
            item.get('university'),
            item.get('group_name'),
            RISK_LABELS.get(item.get('risk'), item.get('risk')),
            item.get('user_rank'),
            official.get('min_rank'),
            official.get('exam_year'),
            official.get('subject_type'),
            official.get('source_url'),
            item.get('label'),
        ]
        writer.writerow([_cell(value) for value in row])
    return '\ufeff' + output.getvalue()


def collection(province: str = '浙江', today: date | None = None) -> dict:
    """征集志愿时间窗：取时间轴中 stage 含「征集」的事件，计算状态与剩余天数。

    days_left：进行中 = 距截止天数；未开始 = 距开始天数；已结束 = 0。
    """
    today = today or date.today()
    payload = load_schedule()
    provinces = payload.get('provinces') or {}
    fallback = province not in provinces
    batches = (payload.get('default') or []) if fallback else provinces[province]
    candidates = []
    for batch in batches:
        if not isinstance(batch, dict):
            continue
        for event in batch.get('events') or []:
            if isinstance(event, dict) and '征集' in str(event.get('stage') or ''):
                candidates.append((batch.get('batch'), event))
    if not candidates:
        return {'province': province, 'batch': None, 'stage': None, 'start': None, 'end': None,
                'days_left': None, 'status': 'unknown',
                'note': '该省录取时间轴暂无征集志愿安排。', 'fallback': fallback}

    states = [(batch, event, _state(event, today)) for batch, event in candidates]
    active = [row for row in states if row[2] == 'active']
    upcoming = [row for row in states if row[2] == 'upcoming']
    if active:
        batch, event, status = active[0]
        end = _as_date(event.get('end'))
        days_left = max(0, (end - today).days) if end else None
        note = f'征集志愿进行中，截止 {event.get("end")}。'
    elif upcoming:
        batch, event, status = min(upcoming, key=lambda row: _as_date(row[1].get('start')) or date.max)
        start = _as_date(event.get('start'))
        days_left = max(0, (start - today).days) if start else None
        note = f'征集志愿将于 {event.get("start")} 开始、{event.get("end")} 结束。'
    else:
        batch, event, status = max(states, key=lambda row: _as_date(row[1].get('end')) or date.min)
        days_left = 0
        note = f'本批次征集志愿已于 {event.get("end")} 结束。'
    if fallback:
        note = f'省份「{province}」时间轴暂未收录，已按通用时间轴展示；' + note
    return {
        'province': province,
        'batch': batch,
        'stage': event.get('stage'),
        'start': event.get('start'),
        'end': event.get('end'),
        'days_left': days_left,
        'status': status,
        'note': note,
        'fallback': fallback,
    }
