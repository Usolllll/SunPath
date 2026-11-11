"""操作审计：只记录动作与目标，不记录密码、令牌或回答正文。"""
from fastapi import Request
from sqlalchemy.orm import Session

from app.models.entities import AuditLog

SENSITIVE_ACTIONS = ('auth.register', 'auth.login', 'auth.logout', 'auth.password',
                     'profile.save', 'plan.create', 'plan.update', 'plan.delete',
                     'plan.submit', 'plan.withdraw', 'plan.export', 'favorite.add', 'favorite.remove')


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        return forwarded.split(',')[0].strip()[:45]
    return (request.client.host if request.client else None)


def log_action(db: Session, user, action: str, target: str | None = None,
               detail: dict | None = None, request: Request | None = None) -> None:
    """写入一条审计记录；由调用方统一 commit，失败不影响主流程时请自行 try/except。"""
    db.add(AuditLog(
        user_id=getattr(user, 'id', None),
        action=action[:40],
        target=(target or '')[:80] or None,
        detail=detail,
        ip=_client_ip(request),
        user_agent=(request.headers.get('user-agent') if request is not None else None) or None,
    ))
