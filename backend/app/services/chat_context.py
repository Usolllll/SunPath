"""Build an owner-scoped, bounded context from persisted user records, never browser drafts."""
import json
from collections import Counter
from datetime import timezone
from sqlalchemy import select, func
from fastapi import HTTPException
from pydantic import ValidationError
from app.models.entities import Plan
from app.schemas.dto import ProfileIn
from app.schemas.chat import ChatContextSummary

MAX_PLANS = 10
MAX_OPTIONS = 50
MAX_CONTEXT_CHARS = 100_000


def profile_data(value):
    if value is None:
        return None
    try:
        return ProfileIn.model_validate(value).model_dump()
    except ValidationError:
        return None


def iso_utc(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.isoformat()


def available_context(db, user):
    total = db.scalar(select(func.count()).select_from(Plan).where(Plan.user_id == user.id))
    plans = db.scalars(select(Plan).where(Plan.user_id == user.id).order_by(Plan.updated_at.desc(), Plan.id.desc()).limit(MAX_OPTIONS)).all()
    return {
        'profile_available': profile_data(user.profile) is not None,
        'saved_plan_count': total, 'max_plans': MAX_PLANS,
        'options_truncated': total > len(plans),
        'plans': [{'id': plan.id, 'name': plan.name, 'group_count': len(plan.items), 'updated_at': iso_utc(plan.updated_at)} for plan in plans],
    }


def plan_data(plan, current_profile):
    snapshot = profile_data(plan.profile_snapshot)
    items = []
    for position, source in enumerate(plan.items, 1):
        university = source.get('university') if isinstance(source, dict) else None
        if not isinstance(university, dict):
            items.append({'position': position, 'data_error': '该条志愿资料不完整，不可推测'})
            continue
        item = {key: source[key] for key in ('id', 'code', 'name', 'majors', 'required_subjects', 'tuition', 'province', 'year', 'seats', 'risk', 'baseline_rank', 'latest_score', 'latest_rank', 'history_rank_min', 'history_rank_max', 'volatility', 'warnings') if key in source}
        item['university'] = {key: university[key] for key in ('name', 'city', 'region', 'level', 'category') if key in university}
        item['history'] = [{key: row[key] for key in ('year', 'score', 'rank') if key in row} for row in source.get('history', []) if isinstance(row, dict)][:3]
        item['position'] = position
        items.append(item)
    counts = Counter(item.get('risk', 'unknown') for item in items)
    return {
        'plan_id': plan.id, 'name': plan.name, 'updated_at': iso_utc(plan.updated_at),
        'data_label': '保存时的模拟志愿快照，不是实时录取数据',
        'profile_snapshot': snapshot,
        'matches_current_profile': snapshot == current_profile if snapshot is not None and current_profile is not None else None,
        'group_count': len(items), 'risk_counts': {risk: counts[risk] for risk in ('reach', 'steady', 'safe', 'unknown')},
        'items': items,
    }


def build_context(db, user, use_profile=True, use_saved_plans=True, plan_ids=None):
    current = profile_data(user.profile) if use_profile else None
    total = db.scalar(select(func.count()).select_from(Plan).where(Plan.user_id == user.id)) if use_saved_plans else 0
    selected = []
    requested = 0
    if use_saved_plans:
        statement = select(Plan).where(Plan.user_id == user.id)
        if plan_ids:
            selected = db.scalars(statement.where(Plan.id.in_(plan_ids))).all()
            if len(selected) != len(plan_ids):
                raise HTTPException(404, '部分方案不存在或不属于当前账号')
            by_id = {plan.id: plan for plan in selected}
            selected = [by_id[plan_id] for plan_id in plan_ids]
            requested = len(plan_ids)
        else:
            selected = db.scalars(statement.order_by(Plan.updated_at.desc(), Plan.id.desc()).limit(MAX_PLANS)).all()
            requested = total
    included = []
    size = 4096 + len(json.dumps(current, ensure_ascii=False))
    for plan in selected:
        entry = plan_data(plan, current)
        entry_size = len(json.dumps(entry, ensure_ascii=False))
        if size + entry_size > MAX_CONTEXT_CHARS:
            break
        included.append(entry)
        size += entry_size
    summary = ChatContextSummary(
        profile_included=current is not None,
        saved_plans_enabled=use_saved_plans,
        total_saved_plans=total,
        requested_plan_count=requested,
        included_plan_count=len(included),
        omitted_plan_count=max(0, requested - len(included)),
        plan_names=[plan['name'] for plan in included],
        max_plans=MAX_PLANS,
    )
    return {'current_profile': current, 'saved_plans': included, 'context_summary': summary.model_dump()}, summary
