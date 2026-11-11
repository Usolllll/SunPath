from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_token, current_user
from app.models.entities import User, Profile
from app.schemas.dto import RegisterIn, LoginIn, UserOut, ProfileIn, NameIn, PasswordIn
from app.services import audit

router = APIRouter(prefix='/auth', tags=['身份与考生信息'])


def _try_audit(db: Session, user, action: str, target: str | None = None,
               request: Request | None = None) -> None:
    """写审计（独立提交）；失败只回滚审计事务，绝不影响主流程响应。

    只记录 action / 目标 / IP / UA，不写密码、令牌或邮箱明文。
    """
    try:
        audit.log_action(db, user, action, target=target, request=request)
        db.commit()
    except Exception:
        db.rollback()


@router.post('/register', status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    user = User(email=body.email, name=body.name, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '该邮箱已注册')
    _try_audit(db, user, 'auth.register', f'user:{user.id}', request)
    return {'access_token': create_token(user), 'token_type': 'bearer', 'user': UserOut.model_validate(user)}

@router.post('/login')
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        # 失败只记动作，不记邮箱/密码；user 为空避免与真实账号关联
        _try_audit(db, None, 'auth.login_failed', None, request)
        raise HTTPException(401, '邮箱或密码不正确')
    _try_audit(db, user, 'auth.login', f'user:{user.id}', request)
    return {'access_token': create_token(user), 'token_type': 'bearer', 'user': UserOut.model_validate(user)}

@router.get('/me', response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user

@router.patch('/me', response_model=UserOut)
def update_me(body: NameIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.name = body.name
    db.commit()
    return user

@router.put('/profile', response_model=UserOut)
def save_profile(body: ProfileIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.profile:
        for key, value in body.model_dump().items():
            setattr(user.profile, key, value)
    else:
        user.profile = Profile(**body.model_dump())
    db.commit()
    _try_audit(db, user, 'profile.save', f'user:{user.id}', request)
    return user

@router.put('/password')
def password(body: PasswordIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, '当前密码不正确')
    if body.current_password == body.new_password:
        raise HTTPException(400, '新密码不能与当前密码相同')
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    db.commit()
    _try_audit(db, user, 'auth.password', f'user:{user.id}', request)
    return {'message': '密码已修改，请重新登录'}

@router.post('/logout')
def logout(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.token_version += 1
    db.commit()
    _try_audit(db, user, 'auth.logout', f'user:{user.id}', request)
    return {'message': '已退出登录'}
