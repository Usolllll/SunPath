import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

PROVINCES = ['浙江', '江苏', '山东', '广东', '河南', '四川']
SUBJECTS = ['物理', '化学', '生物', '历史', '政治', '地理']

class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('请输入有效的邮箱地址')
        return value

class RegisterIn(LoginIn):
    name: str = Field(min_length=1, max_length=40)

    @field_validator('name')
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError('姓名不能为空')
        return v.strip()

class ProfileIn(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    province: Literal['浙江', '江苏', '山东', '广东', '河南', '四川']
    exam_year: int = Field(ge=2024, le=2030)
    score: int = Field(ge=0, le=750)
    rank: int = Field(ge=1, le=2_000_000)
    subjects: list[str] = Field(min_length=3, max_length=3)
    regions: list[str] = Field(default_factory=list, max_length=10)
    majors: list[str] = Field(default_factory=list, max_length=10)

    @field_validator('subjects')
    @classmethod
    def valid_subjects(cls, v):
        if len(set(v)) != 3 or any(s not in SUBJECTS for s in v):
            raise ValueError('请选择三门不同的有效选考科目')
        return v

    @field_validator('regions', 'majors')
    @classmethod
    def valid_preferences(cls, v):
        if any(not s.strip() or len(s) > 30 for s in v):
            raise ValueError('偏好名称应为 1–30 个字符')
        return list(dict.fromkeys(s.strip() for s in v))

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str
    profile: ProfileIn | None

class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)

    @field_validator('name')
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError('姓名不能为空')
        return v.strip()

class PasswordIn(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

class PlanIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    group_ids: list[int] = Field(min_length=1, max_length=30)

    @field_validator('name')
    @classmethod
    def plan_name(cls, v):
        if not v.strip():
            raise ValueError('方案名称不能为空')
        return v.strip()

    @field_validator('group_ids')
    @classmethod
    def unique_ids(cls, v):
        if len(set(v)) != len(v):
            raise ValueError('方案中不能重复添加同一专业组')
        return v
