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
    # v2 决策维度（全部可选，缺省不改变一期行为）
    priority_mode: Literal['school', 'balanced', 'major'] = 'balanced'
    interests: dict[str, int] | None = None
    budget_total: int | None = Field(default=None, ge=0, le=2_000_000)
    physical: dict[str, object] | None = None
    intent_types: list[str] | None = None
    subscription: dict[str, object] | None = None
    # v3 加分与专项资格：只登记，不自动折算位次（省考试院认定为准）
    bonus_points: int = Field(default=0, ge=0, le=20)
    bonus_type: Literal['none', 'minority', 'martyr', 'overseas_chinese', 'veteran', 'other'] = 'none'
    special_programs: list[Literal['国家专项', '地方专项', '高校专项']] = Field(default_factory=list, max_length=3)

    @field_validator('special_programs')
    @classmethod
    def unique_special_programs(cls, v):
        return list(dict.fromkeys(v))

    @field_validator('bonus_points', 'bonus_type', 'special_programs', mode='before')
    @classmethod
    def bonus_defaults(cls, v, info):
        """历史画像可能没有这些字段（NULL），按缺省值处理，避免回读报错。"""
        if v is not None:
            return v
        return {'bonus_points': 0, 'bonus_type': 'none', 'special_programs': []}[info.field_name]

    @field_validator('subscription')
    @classmethod
    def valid_subscription(cls, v):
        if v is None:
            return None
        allowed_types = {'collection', 'policy', 'lecture', 'quality', 'plan', 'result'}
        types = v.get('types') or []
        if [item for item in types if item not in allowed_types]:
            raise ValueError('订阅类型只能是 collection/policy/lecture/quality/plan/result')
        channel = v.get('channel', 'site')
        if channel not in {'site'}:
            raise ValueError('当前仅支持站内信渠道')
        lead_days = v.get('lead_days', 3)
        if not isinstance(lead_days, int) or not 0 <= lead_days <= 14:
            raise ValueError('提前提醒天数应为 0–14 的整数')
        return {'types': list(dict.fromkeys(types)), 'channel': channel, 'lead_days': lead_days}

    @field_validator('priority_mode', mode='before')
    @classmethod
    def default_priority_mode(cls, v):
        return 'balanced' if v is None else v

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

    @field_validator('interests')
    @classmethod
    def valid_interests(cls, v):
        if v is None:
            return None
        allowed = {'R', 'I', 'A', 'S', 'E', 'C'}
        if set(v) - allowed:
            raise ValueError('兴趣维度只能是 RIASEC 六型')
        result = {}
        for key in allowed:
            value = v.get(key, 0)
            if not 0 <= value <= 100:
                raise ValueError('兴趣分应在 0–100 之间')
            result[key] = int(value)
        return result

    @field_validator('physical')
    @classmethod
    def valid_physical(cls, v):
        if v is None:
            return None
        allowed = {'color_weak', 'color_blind', 'naked_vision', 'corrected_vision', 'hearing', 'smell', 'hbsag'}
        return {key: value for key, value in v.items() if key in allowed}

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

BATCHES = ['本科批', '专科批']

class PlanIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    group_ids: list[int] = Field(min_length=1, max_length=30)
    # v3: 填报批次（缺省本科批；只做方案归属，不改变推荐候选池）
    batch: Literal['本科批', '专科批'] = '本科批'

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

class ImportPlanIn(BaseModel):
    """志愿表 CSV 导入：name 可选（缺省自动命名），content 为整份 CSV 文本。"""
    name: str | None = Field(default=None, max_length=80)
    batch: Literal['本科批', '专科批'] = '本科批'
    content: str = Field(min_length=1, max_length=200000)

    @field_validator('name')
    @classmethod
    def import_name(cls, v):
        if v is None:
            return None
        value = v.strip()
        if not value:
            raise ValueError('方案名称不能为空')
        return value

class FavoriteIn(BaseModel):
    """收藏院校；只收院校 id，院校是否存在由接口校验。"""
    university_id: int = Field(gt=0)
