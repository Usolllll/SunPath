"""敏感信息脱敏与权限审计（FR-M10-03）。

管理员可见的账号与权限视图：邮箱一律脱敏（``a***@domain``），不返回密码哈希、
令牌或明文联系方式；审计动作只返回动作名、目标与时间。
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import AuditLog, User
from app.services.config_view import mask_email

ADMIN_ACTIONS = ('batch.update', 'report.export', 'data_version.review')


def build(db: Session) -> dict:
    admin_emails = set(get_settings().admin_emails)
    users = db.scalars(select(User).order_by(User.id)).all()
    admins = [user for user in users if (user.email or '').lower() in admin_emails]
    candidates = [user for user in users if (user.email or '').lower() not in admin_emails]
    recent_logins = db.execute(
        select(AuditLog, User)
        .join(User, AuditLog.user_id == User.id)
        .where(AuditLog.action == 'auth.login')
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(8)
    ).all()
    admin_actions = db.execute(
        select(AuditLog, User)
        .join(User, AuditLog.user_id == User.id)
        .where(AuditLog.action.in_(ADMIN_ACTIONS))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(8)
    ).all()
    denied = int(db.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == 'permission.denied')
    ) or 0)
    return {
        'users': {
            'total': len(users),
            'admins': len(admins),
            'candidates': len(candidates),
        },
        'admins': [{'email': mask_email(user.email), 'name': user.name} for user in admins],
        'recent_logins': [{
            'email': mask_email(user.email),
            'at': row.created_at.isoformat() if row.created_at else None,
        } for row, user in recent_logins],
        'admin_actions': [{
            'action': row.action,
            'target': row.target,
            'email': mask_email(user.email),
            'at': row.created_at.isoformat() if row.created_at else None,
        } for row, user in admin_actions],
        'denied_count': denied,
        'note': '邮箱已脱敏；密码哈希、令牌与明文联系方式不返回。',
    }
