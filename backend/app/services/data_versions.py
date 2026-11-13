"""数据版本审核与发布（FR-M3-05）。

DataVersion 是官方数据（高校名单 / 投档线 / 招生计划 / 一分一段等）的版本台账，
每个官方文件一行，``is_current`` 标记当前生效版本。本模块补上「审核 + 发布」流程：

- 新版导入默认 ``review_status='pending'``，管理员审核通过后写入审核人与时间；
- 审核通过即发布：同一 ``dataset + province + exam_year`` 下仅该版本 ``is_current=True``，
  旧版本自动转为历史版本（不删除任何数据）；
- 审核驳回保留在台账中，不会被任何查询当作当前版本使用。
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import DataVersion

REVIEW_LABELS = {'pending': '待审核', 'approved': '已通过', 'rejected': '已驳回'}
DECISIONS = {'approved', 'rejected'}


class DataVersionError(ValueError):
    """审核参数不合法。"""


def utcnow():
    return datetime.now(timezone.utc)


def serialize(version: DataVersion) -> dict:
    return {
        'id': version.id,
        'dataset': version.dataset,
        'province': version.province,
        'exam_year': version.exam_year,
        'source_url': version.source_url,
        'attachment_url': version.attachment_url,
        'published_at': version.published_at,
        'fetched_at': version.fetched_at,
        'parser_version': version.parser_version,
        'doc_status': version.doc_status,
        'row_count': version.row_count,
        'is_current': bool(version.is_current),
        'review_status': version.review_status or 'pending',
        'review_status_label': REVIEW_LABELS.get(version.review_status or 'pending', '未知'),
        'reviewed_by': version.reviewed_by,
        'reviewed_at': version.reviewed_at.isoformat() if version.reviewed_at else None,
        'review_note': version.review_note,
        'content_sha256': version.content_sha256,
        'note': version.note,
        'created_at': version.created_at.isoformat() if version.created_at else None,
    }


def list_versions(db: Session, status: str | None = None) -> dict:
    statement = select(DataVersion)
    if status:
        statement = statement.where(DataVersion.review_status == status)
    rows = db.scalars(
        statement.order_by(DataVersion.dataset, DataVersion.province, DataVersion.created_at.desc(), DataVersion.id.desc())
    ).all()
    all_rows = db.scalars(select(DataVersion)).all()
    counts = {'pending': 0, 'approved': 0, 'rejected': 0}
    for row in all_rows:
        counts[row.review_status or 'pending'] = counts.get(row.review_status or 'pending', 0) + 1
    return {
        'total': len(rows),
        'counts': counts,
        'current': sum(1 for row in all_rows if row.is_current),
        'items': [serialize(row) for row in rows],
        'note': '审核通过即发布为当前版本；旧版本保留为历史版本，不删除任何数据。',
    }


def review(db: Session, version: DataVersion, decision: str, note: str | None, reviewer: str) -> dict:
    if decision not in DECISIONS:
        raise DataVersionError('审核结论只能是 approved 或 rejected')
    version.review_status = decision
    version.reviewed_by = reviewer
    version.reviewed_at = utcnow()
    version.review_note = (note or '').strip()[:200] or None
    if decision == 'approved':
        # 发布：同一数据集 + 省份 + 年份只保留一个当前版本
        siblings = db.scalars(
            select(DataVersion).where(
                DataVersion.dataset == version.dataset,
                DataVersion.province == version.province,
                DataVersion.id != version.id,
            )
        ).all()
        for sibling in siblings:
            if (sibling.exam_year or None) == (version.exam_year or None):
                sibling.is_current = False
        version.is_current = True
    else:
        # 驳回的版本不能作为当前版本
        version.is_current = False
    db.flush()
    return serialize(version)
