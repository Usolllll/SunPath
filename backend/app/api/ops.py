"""运营与数据质量接口（FR-M9-04 / FR-M9-02 / FR-M8-04 / FR-M10-02 / FR-M1-05）。

由 D6-RTM 批次实现；所有查询需登录，审计日志仅返回本人记录。
- ``/audit``、``/profile-completeness``：需登录，且只处理当前用户数据；
- ``/faq``、``/dictionary``、``/data-quality``、``/popularity``：公开只读，便于运营页直接展示。
"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_user, require_admin
from app.models.entities import AuditLog, Favorite, University, User
from app.services import audit
from app.services import dictionary as dictionary_service
from app.services import faq as faq_service
from app.services import quality as quality_service
from app.services import report as report_service

router = APIRouter(prefix='/ops', tags=['运营与数据质量'])

# 画像完整度权重（合计 100）：基础四要素权重最高，偏好与决策维度次之。
COMPLETENESS_WEIGHTS = (
    ('province', 10), ('exam_year', 5), ('score', 15), ('rank', 15), ('subjects', 10),
    ('regions', 10), ('majors', 10), ('priority_mode', 5), ('interests', 10),
    ('budget_total', 5), ('physical', 5),
)


def _has_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _serialize_audit(row: AuditLog) -> dict:
    return {
        'id': row.id,
        'action': row.action,
        'target': row.target,
        'detail': row.detail,
        'ip': row.ip,
        'created_at': row.created_at.isoformat() if row.created_at else None,
    }


@router.get('/audit')
def audit_logs(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    """本人操作审计（按时间倒序）；绝不返回其他账号记录。"""
    condition = AuditLog.user_id == user.id
    total = int(db.scalar(select(func.count()).select_from(AuditLog).where(condition)) or 0)
    rows = db.scalars(
        select(AuditLog).where(condition)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset).limit(limit)
    ).all()
    return {'total': total, 'limit': limit, 'offset': offset,
            'items': [_serialize_audit(row) for row in rows]}


@router.get('/faq')
def faq(q: str = Query('', max_length=80), category: str = Query('', max_length=40)):
    """FAQ 模糊检索：命中 question / keywords / answer；category 为空表示全部分类。"""
    return faq_service.search(q, category)


@router.get('/dictionary')
def data_dictionary():
    """数据字典：省份/选科/层次/城市等级/批次/模式权重/风险档/预算档/数据源。"""
    return dictionary_service.build()


@router.get('/data-quality')
def data_quality(db: Session = Depends(get_db)):
    """数据质量看板：模拟库计数、真实数据覆盖、当前版本台账、巡检结果与行为计数。"""
    return quality_service.dashboard(db)


@router.get('/popularity')
def popularity(response: Response, limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    """收藏热度：来自真实用户收藏行为（非模拟），按收藏数倒序。

    返回数组（与前端 ``PopularityItem[]`` 契约一致）；附加说明放在响应头
    ``X-Popularity-Note``（UTF-8 百分号编码，客户端 unquote 后为中文），
    收藏为空时数组为 ``[]`` 且说明为"暂无用户收藏数据"。
    """
    favorites = func.count(Favorite.id).label('favorites')
    rows = db.execute(
        select(University, favorites)
        .join(Favorite, Favorite.university_id == University.id)
        .group_by(University.id)
        .order_by(favorites.desc(), University.name)
        .limit(limit)
    ).all()
    items = [{
        'university_id': university.id,
        'name': university.name,
        'city': university.city,
        'region': university.region,
        'level': university.level,
        'level_tier': university.level_tier,
        'favorites': int(count),
    } for university, count in rows]
    note = '收藏热度来自真实用户收藏行为（非模拟数据）。' if items else '暂无用户收藏数据。'
    # HTTP header 只允许 latin-1，故用百分号编码携带中文说明
    response.headers['X-Popularity-Note'] = quote(note, safe='')
    return items


@router.get('/profile-completeness')
def profile_completeness(user: User = Depends(current_user)):
    """画像完整度（0–100）：按字段是否已填写加权，返回已填/缺失字段清单。"""
    profile = user.profile
    filled: list[str] = []
    missing: list[str] = []
    score = 0
    for field, weight in COMPLETENESS_WEIGHTS:
        if profile is not None and _has_value(getattr(profile, field, None)):
            filled.append(field)
            score += weight
        else:
            missing.append(field)
    return {'score': score, 'filled': filled, 'missing': missing}


# ---------------------------------------------------------------- 管理员看板（M9）
@router.get('/behavior')
def behavior(days: int = Query(30, ge=7, le=90),
             admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """行为看板（仅管理员）：注册/建方案/提交/投档结果查询/收藏，按天补零。"""
    return report_service.behavior(db, days)


@router.get('/tier-distribution')
def tier_distribution(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """梯度分布（仅管理员）：遍历已保存方案的 risk 字段统计冲稳保。"""
    return report_service.tier_distribution(db)


@router.get('/report')
def operations_report(days: int = Query(30, ge=7, le=90),
                      admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """运营报表（仅管理员）：用户/方案/收藏/消息/梯度/行为/数据质量汇总。"""
    return report_service.report(db, days)


@router.get('/report/export')
def report_export(request: Request, days: int = Query(30, ge=7, le=90),
                  admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """导出运营报表 CSV（仅管理员；UTF-8 BOM + safe_cell 防公式注入，写审计）。"""
    result = report_service.report(db, days)
    audit.log_action(db, admin, 'report.export', target=f'report:{days}d',
                     detail={'days': days, 'format': 'csv'}, request=request)
    db.commit()
    return Response(
        content=report_service.report_csv(result).encode('utf-8'),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{report_service.report_filename()}"'},
    )
