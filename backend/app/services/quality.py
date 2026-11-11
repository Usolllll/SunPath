"""数据质量看板（FR-M9-04）：模拟库 / 真实数据 / 版本台账 / 巡检结果 / 行为计数。

全部为只读统计，不修改任何业务数据；巡检报告读取 ``backend/reports/patrol_*.json``
最新一份，缺失时返回 ``None``（前端显示"尚无巡检记录"）。
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.models.entities import (Admission, AuditLog, DataVersion, Enrollment, Favorite,
                                 MajorCatalog, MajorGroup, Plan, University)
from app.services import faq as faq_service
from app.services import real_data

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPORT_DIR = BACKEND_DIR / 'reports'
PATROL_GLOB = 'patrol_*.json'
DISCLAIMER = ('模拟样本仅用于演示产品流程；真实投档数据来自各省教育考试院公开发布文件，'
              '只作核对参考，不构成录取预测。')
PATROL_FIELDS = ('id', 'dataset', 'ok', 'status', 'changed', 'checked_at')


def _count(db, model) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def latest_patrol() -> dict | None:
    """读取最新一份巡检报告；文件缺失或损坏时返回 None（不抛错）。"""
    try:
        files = sorted(REPORT_DIR.glob(PATROL_GLOB))
    except OSError:
        return None
    if not files:
        return None
    latest = files[-1]
    try:
        payload = json.loads(latest.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    items = []
    for item in payload.get('items') or []:
        if not isinstance(item, dict):
            continue
        if item.get('skipped'):
            # 人工/合规跳过的源：不伪造 ok，显式标记 skipped 与原因
            items.append({'id': item.get('id'), 'dataset': item.get('dataset'), 'ok': None,
                          'status': None, 'changed': None, 'checked_at': item.get('checked_at'),
                          'skipped': True, 'reason': item.get('reason')})
            continue
        items.append({'id': item.get('id'), 'dataset': item.get('dataset'),
                      'ok': None if item.get('ok') is None else bool(item.get('ok')),
                      'status': item.get('status'), 'changed': item.get('changed'),
                      'checked_at': item.get('checked_at')})
    return {'last_checked_at': payload.get('checked_at'), 'report_file': latest.name, 'items': items}


def current_versions(db) -> list[dict]:
    rows = db.scalars(
        select(DataVersion)
        .where(DataVersion.is_current.is_(True))
        .order_by(DataVersion.dataset, DataVersion.province, DataVersion.exam_year)
    ).all()
    return [{
        'dataset': row.dataset, 'province': row.province, 'exam_year': row.exam_year,
        'row_count': row.row_count, 'published_at': row.published_at,
        'fetched_at': row.fetched_at, 'source_url': row.source_url,
        'doc_status': row.doc_status, 'content_sha256': row.content_sha256,
    } for row in rows]


def dashboard(db) -> dict:
    real = real_data.summary(db)
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'simulated': {
            'universities': _count(db, University),
            'groups': _count(db, MajorGroup),
            'admissions': _count(db, Admission),
            'enrollments': _count(db, Enrollment),
            'major_cards': _count(db, MajorCatalog),
        },
        'real': {
            'total_rows': real.get('total_rows', 0),
            'provinces': real.get('provinces', []),
            'note': real.get('note'),
            'disclaimer': real.get('disclaimer'),
        },
        'versions': current_versions(db),
        'patrol': latest_patrol(),
        'counts': {
            'favorites': _count(db, Favorite),
            'audit_logs': _count(db, AuditLog),
            'plans': _count(db, Plan),
            'faq': len(faq_service.load_items()),
        },
        'disclaimer': DISCLAIMER,
    }
