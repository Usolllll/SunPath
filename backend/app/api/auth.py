from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_token, current_user
from app.models.entities import User, Profile
from app.schemas.dto import RegisterIn, LoginIn, UserOut, ProfileIn, NameIn, PasswordIn

router = APIRouter(prefix='/auth', tags=['身份与考生信息'])

@router.post('/register', status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    user = User(email=body.email, name=body.name, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '该邮箱已注册')
    return {'access_token': create_token(user), 'token_type': 'bearer', 'user': UserOut.model_validate(user)}

@router.post('/login')
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, '邮箱或密码不正确')
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
def save_profile(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.profile:
        for key, value in body.model_dump().items():
            setattr(user.profile, key, value)
    else:
        user.profile = Profile(**body.model_dump())
    db.commit()
    return user

@router.put('/password')
def password(body: PasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, '当前密码不正确')
    if body.current_password == body.new_password:
        raise HTTPException(400, '新密码不能与当前密码相同')
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    db.commit()
    return {'message': '密码已修改，请重新登录'}

@router.post('/logout')
def logout(user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.token_version += 1
    db.commit()
    return {'message': '已退出登录'}
