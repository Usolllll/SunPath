"""真实投档数据查询（与一期模拟数据物理隔离；只读官方字段，逐条带来源）。"""
from sqlalchemy import func, select

from app.models.entities import DataVersion, RealAdmission

NOTE = '真实投档数据来自各省教育考试院公开发布文件，已按来源 URL + 发布时间 + 文件哈希入库；仅作核对参考。'


def summary(db):
    rows = db.execute(
        select(
            RealAdmission.province,
            func.count().label('rows'),
            func.count(func.distinct(RealAdmission.school_name)).label('schools'),
            func.min(RealAdmission.exam_year).label('year_min'),
            func.max(RealAdmission.exam_year).label('year_max'),
            func.max(RealAdmission.published_at).label('published_at'),
        ).group_by(RealAdmission.province).order_by(RealAdmission.province)
    ).all()
    years = {}
    for row in rows:
        years[row.province] = [value[0] for value in db.execute(
            select(RealAdmission.exam_year).where(RealAdmission.province == row.province)
            .distinct().order_by(RealAdmission.exam_year)
        ).all()]
    versions = {}
    for version in db.scalars(select(DataVersion).where(DataVersion.is_current.is_(True))).all():
        versions.setdefault(version.province, []).append({
            'dataset': version.dataset, 'row_count': version.row_count,
            'published_at': version.published_at, 'source_url': version.source_url,
            'fetched_at': version.fetched_at, 'doc_status': version.doc_status,
        })
    provinces = []
    for row in rows:
        provinces.append({
            'province': row.province, 'rows': row.rows, 'schools': row.schools,
            'years': years.get(row.province, []),
            'published_at': row.published_at,
            'versions': versions.get(row.province, []),
        })
    return {
        'total_rows': sum(item['rows'] for item in provinces),
        'provinces': provinces,
        'note': NOTE,
        'disclaimer': '真实投档线不等于录取线，也不代表今年录取结果；正式填报以省考试院当年公布为准。',
    }


def list_rows(db, province, year=None, query='', page=1, page_size=50):
    statement = select(RealAdmission).where(RealAdmission.province == province)
    if year:
        statement = statement.where(RealAdmission.exam_year == year)
    if query:
        statement = statement.where(RealAdmission.school_name.contains(query.strip()))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(
        statement.order_by(RealAdmission.exam_year.desc(), RealAdmission.school_name, RealAdmission.min_rank)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        'total': total,
        'items': [{
            'id': row.id, 'school_name': row.school_name, 'exam_year': row.exam_year,
            'subject_type': row.subject_type, 'batch': row.batch, 'round_no': row.round_no,
            'group_name': row.group_name, 'major_name': row.major_name,
            'min_score': row.min_score, 'min_rank': row.min_rank,
            'required_subjects': row.required_subjects,
            'source_url': row.source_url, 'published_at': row.published_at,
        } for row in rows],
        'note': NOTE,
    }


def school_official(db, school_name, province):
    """该校该省最近一年的真实投档最低位次（用于与模拟参考位次做"官方核对"）。"""
    row = db.scalars(
        select(RealAdmission)
        .where(RealAdmission.school_name == school_name, RealAdmission.province == province,
               RealAdmission.min_rank.is_not(None))
        .order_by(RealAdmission.exam_year.desc(), RealAdmission.min_rank)
    ).first()
    if not row:
        return None
    return {
        'exam_year': row.exam_year,
        'subject_type': row.subject_type,
        'group_name': row.group_name,
        'major_name': row.major_name,
        'min_score': row.min_score,
        'min_rank': row.min_rank,
        'source_url': row.source_url,
        'published_at': row.published_at,
        'data_label': '官方投档数据',
    }


def attach_official(db, items, province):
    """给推荐结果挂真实数据核对信息；无真实数据则 official=None（不推测）。"""
    cache = {}
    for item in items:
        name = (item.get('university') or {}).get('name')
        if not name:
            item['official'] = None
            continue
        if name not in cache:
            cache[name] = school_official(db, name, province)
        item['official'] = cache[name]
    return items
