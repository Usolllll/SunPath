from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.models.entities import MajorGroup

DISCLAIMER = '全部招生与录取数据为模拟样本；冲稳保为规则估算，不代表真实录取概率。正式填报请以省考试院及高校当年公布的信息为准。'

def load_groups(db: Session):
    return db.scalars(select(MajorGroup).options(selectinload(MajorGroup.university), selectinload(MajorGroup.admissions), selectinload(MajorGroup.enrollments))).all()

def serialize_group(group, province, year, with_plan_trend=False):
    university = group.university
    history = sorted([a for a in group.admissions if a.province == province and year - 3 <= a.year < year], key=lambda a: a.year)
    enrollment = next((p for p in group.enrollments if p.province == province and p.year == year), None)
    result = {
        'id': group.id, 'code': group.code, 'name': group.name, 'majors': group.majors,
        'required_subjects': group.required_subjects, 'tuition': group.tuition,
        'tuition_type': group.tuition_type, 'accommodation': group.accommodation,
        'duration_years': group.duration_years, 'major_category': group.major_category,
        'cost_year': group.cost_year,
        'university': {'id': university.id, 'name': university.name, 'city': university.city, 'region': university.region, 'level': university.level, 'category': university.category, 'description': university.description, 'initials': university.initials, 'color': university.color,
                       'level_tier': university.level_tier, 'city_tier': university.city_tier,
                       'transfer_friendly': university.transfer_friendly, 'transfer_notes': university.transfer_notes,
                       'transfer_year': university.transfer_year, 'official_url': university.official_url},
        'province': province, 'year': year, 'seats': enrollment.count if enrollment else 0,
        'history': [{'year': a.year, 'score': a.min_score, 'rank': a.min_rank} for a in history],
        'latest_rank': history[-1].min_rank if history else None,
        'latest_score': history[-1].min_score if history else None,
        'data_label': '模拟数据',
    }
    if with_plan_trend:
        trend = sorted(
            [{'year': p.year, 'seats': p.count} for p in group.enrollments if p.province == province],
            key=lambda item: item['year'],
        )
        for index, item in enumerate(trend):
            previous = trend[index - 1]['seats'] if index else None
            item['change'] = None if previous in (None, 0) else round((item['seats'] - previous) / previous * 100, 1)
        result['plan_trend'] = trend
        result['plan_trend_label'] = '模拟样本 · 计划数仅用于演示'
    return result

def require_profile(user):
    if not user.profile:
        raise HTTPException(400, '请先完善考生画像')
    return user.profile
