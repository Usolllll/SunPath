"""真实投档数据查询（与一期模拟数据物理隔离；只读官方字段，逐条带来源）。

数据既有省级投档线，也有专业级投档/招生计划（parser_version 区分）。院校级
查询（school_official）对同一院校同一年代的多专业行做聚合：取 **最大 min_rank**
（最靠后的最低位次）作为院校投档最低位次的保守口径，用 major_level / aggregated_rows
标明这是专业级数据的聚合结果。
"""
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
        parser_versions = [value[0] for value in db.execute(
            select(RealAdmission.parser_version).where(RealAdmission.province == row.province)
            .distinct().order_by(RealAdmission.parser_version)
        ).all()]
        provinces.append({
            'province': row.province, 'rows': row.rows, 'schools': row.schools,
            'years': years.get(row.province, []),
            'published_at': row.published_at,
            'parser_versions': parser_versions,
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
            'id': row.id, 'school_name': row.school_name, 'national_code': row.national_code,
            'exam_year': row.exam_year, 'subject_type': row.subject_type,
            'admission_type': row.admission_type, 'batch': row.batch, 'round_no': row.round_no,
            'group_code': row.group_code, 'group_name': row.group_name, 'major_name': row.major_name,
            'min_score': row.min_score, 'min_rank': row.min_rank,
            'max_score': row.max_score, 'avg_score': row.avg_score,
            'actual_count': row.actual_count, 'plan_count': row.plan_count,
            'required_subjects': row.required_subjects,
            'source_url': row.source_url, 'published_at': row.published_at,
        } for row in rows],
        'note': NOTE,
    }


def school_official(db, school_name, province):
    """该校该省最近一年真实投档数据的院校级代表值。

    专业级数据（一个院校同一年多专业/多专业组行）取 **最大 min_rank** 作为
    院校投档最低位次的保守口径（最靠后的最低位次），并返回 major_level /
    aggregated_rows 说明聚合口径。
    """
    latest_year = db.scalar(
        select(func.max(RealAdmission.exam_year)).where(
            RealAdmission.school_name == school_name,
            RealAdmission.province == province,
            RealAdmission.min_rank.is_not(None),
        )
    )
    if latest_year is None:
        return None
    rows = db.scalars(
        select(RealAdmission).where(
            RealAdmission.school_name == school_name,
            RealAdmission.province == province,
            RealAdmission.exam_year == latest_year,
            RealAdmission.min_rank.is_not(None),
        )
    ).all()
    if not rows:
        return None
    # 最大 min_rank = 该校该年最靠后的最低位次（保守的院校投档最低位次）
    representative = max(rows, key=lambda row: (row.min_rank, row.id or 0))
    return {
        'exam_year': representative.exam_year,
        'subject_type': representative.subject_type,
        'group_name': representative.group_name,
        'major_name': representative.major_name,
        'min_score': representative.min_score,
        'min_rank': representative.min_rank,
        'source_url': representative.source_url,
        'published_at': representative.published_at,
        'data_label': '官方投档数据',
        'major_level': True,
        'aggregated_rows': len(rows),
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
