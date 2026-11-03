import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import User

bearer = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600_000).hex()
    return f'pbkdf2_sha256$600000${salt}${digest}'

def verify_password(password: str, encoded: str) -> bool:
    try:
        _, iterations, salt, expected = encoded.split('$')
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(iterations)).hex()
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False

def create_token(user: User):
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(user.id), 'ver': user.token_version, 'iat': now, 'exp': now + timedelta(minutes=settings.jwt_expire_minutes)}, settings.jwt_secret, algorithm='HS256')

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    error = HTTPException(status_code=401, detail='登录已过期，请重新登录')
    if not credentials:
        raise error
    try:
        claims = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=['HS256'], options={'require': ['sub', 'exp', 'iat', 'ver']})
        user = db.get(User, int(claims['sub']))
        if not user or user.token_version != claims['ver']:
            raise error
        return user
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise error
