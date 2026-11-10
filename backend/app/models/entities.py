from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, ForeignKey, JSON, DateTime, UniqueConstraint, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(40))
    password_hash: Mapped[str] = mapped_column(String(256))
    token_version: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    profile: Mapped['Profile | None'] = relationship(back_populates='user', cascade='all, delete-orphan', uselist=False)

class Profile(Base):
    __tablename__ = 'profiles'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), unique=True)
    province: Mapped[str] = mapped_column(String(20))
    exam_year: Mapped[int] = mapped_column(Integer)
    score: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int] = mapped_column(Integer)
    subjects: Mapped[list] = mapped_column(JSON)
    regions: Mapped[list] = mapped_column(JSON)
    majors: Mapped[list] = mapped_column(JSON)
    # v2: 偏好与决策维度（全部可空；缺失时按一期行为回退）
    priority_mode: Mapped[str | None] = mapped_column(String(10), default='balanced')      # school / balanced / major
    interests: Mapped[dict | None] = mapped_column(JSON, default=None)                      # RIASEC {R,I,A,S,E,C}
    budget_total: Mapped[int | None] = mapped_column(Integer, default=None)                  # 四年总预算（元）
    physical: Mapped[dict | None] = mapped_column(JSON, default=None)                        # 体检项
    intent_types: Mapped[list | None] = mapped_column(JSON, default=None)                    # 强基/综评/专项...
    user: Mapped['User'] = relationship(back_populates='profile')

class University(Base):
    __tablename__ = 'universities'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    city: Mapped[str] = mapped_column(String(30))
    region: Mapped[str] = mapped_column(String(20))
    level: Mapped[str] = mapped_column(String(30))
    category: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(String(500))
    initials: Mapped[str] = mapped_column(String(6))
    color: Mapped[str] = mapped_column(String(12))
    # v2: 院校维度（由 level_scores.json / city_tiers.json 映射，不全为数据事实）
    level_tier: Mapped[int | None] = mapped_column(Integer, default=None)                   # 0-100，内部排序用
    city_tier: Mapped[int | None] = mapped_column(Integer, default=None)                    # 1 一线 / 2 新一线 / 3 二线 / 4 三线及以下
    transfer_friendly: Mapped[int | None] = mapped_column(Integer, default=None)            # 1 严格 / 2 一般 / 3 宽松；null=未收录
    transfer_notes: Mapped[str | None] = mapped_column(String(300), default=None)
    transfer_source_url: Mapped[str | None] = mapped_column(String(500), default=None)
    transfer_year: Mapped[int | None] = mapped_column(Integer, default=None)
    official_url: Mapped[str | None] = mapped_column(String(500), default=None)             # 本科招生网/招生章程
    groups: Mapped[list['MajorGroup']] = relationship(back_populates='university')

class MajorGroup(Base):
    __tablename__ = 'major_groups'
    id: Mapped[int] = mapped_column(primary_key=True)
    university_id: Mapped[int] = mapped_column(ForeignKey('universities.id'), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(80))
    majors: Mapped[list] = mapped_column(JSON)
    required_subjects: Mapped[list] = mapped_column(JSON)
    tuition: Mapped[int] = mapped_column(Integer)
    # v2: 预算维度
    tuition_type: Mapped[str | None] = mapped_column(String(20), default=None)               # 公办 / 民办 / 中外合作
    accommodation: Mapped[int | None] = mapped_column(Integer, default=None)                # 元/年
    duration_years: Mapped[int | None] = mapped_column(Integer, default=4)
    major_category: Mapped[str | None] = mapped_column(String(20), default=None)            # 教育部 13 门类之一
    degree_type: Mapped[str | None] = mapped_column(String(20), default=None)
    cost_source_url: Mapped[str | None] = mapped_column(String(500), default=None)
    cost_year: Mapped[int | None] = mapped_column(Integer, default=None)
    university: Mapped['University'] = relationship(back_populates='groups')
    admissions: Mapped[list['Admission']] = relationship(back_populates='group')
    enrollments: Mapped[list['Enrollment']] = relationship(back_populates='group')

class Admission(Base):
    __tablename__ = 'admissions'
    __table_args__ = (UniqueConstraint('group_id', 'province', 'year'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey('major_groups.id'), index=True)
    province: Mapped[str] = mapped_column(String(20), index=True)
    year: Mapped[int] = mapped_column(Integer)
    min_score: Mapped[int] = mapped_column(Integer)
    min_rank: Mapped[int] = mapped_column(Integer)
    group: Mapped['MajorGroup'] = relationship(back_populates='admissions')

class Enrollment(Base):
    __tablename__ = 'enrollments'
    __table_args__ = (UniqueConstraint('group_id', 'province', 'year'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey('major_groups.id'), index=True)
    province: Mapped[str] = mapped_column(String(20), index=True)
    year: Mapped[int] = mapped_column(Integer)
    count: Mapped[int] = mapped_column(Integer)
    group: Mapped['MajorGroup'] = relationship(back_populates='enrollments')

class Plan(Base):
    __tablename__ = 'plans'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[str] = mapped_column(String(80))
    items: Mapped[list] = mapped_column(JSON)
    profile_snapshot: Mapped[dict] = mapped_column(JSON)
    # v2: 决策快照（历史方案照原样展示，不因新逻辑被重新解释）
    mode: Mapped[str | None] = mapped_column(String(10), default=None)
    weights_snapshot: Mapped[dict | None] = mapped_column(JSON, default=None)
    budget_snapshot: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RealAdmission(Base):
    """官方真实投档数据（与一期模拟数据物理隔离）。"""
    __tablename__ = 'real_admissions'
    __table_args__ = (
        UniqueConstraint('province', 'exam_year', 'subject_type', 'batch', 'round_no', 'group_code',
                         'group_name', 'major_name', 'school_name', 'admission_type',
                         name='uq_real_admission'),
        Index('ix_real_admission_province_year', 'province', 'exam_year'),
        Index('ix_real_admission_school', 'school_name'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    school_name: Mapped[str] = mapped_column(String(80))
    national_code: Mapped[str | None] = mapped_column(String(10), default=None)             # 教育部标识码后 5 位；无则空
    province: Mapped[str] = mapped_column(String(20))
    exam_year: Mapped[int] = mapped_column(Integer)
    subject_type: Mapped[str] = mapped_column(String(20))                                   # 历史类/物理类/综合改革/理工/文史
    admission_type: Mapped[str | None] = mapped_column(String(20), default=None)
    batch: Mapped[str | None] = mapped_column(String(30), default=None)
    round_no: Mapped[str | None] = mapped_column(String(20), default=None)                  # 首次投档/第2次志愿/征集
    group_code: Mapped[str | None] = mapped_column(String(30), default=None)
    group_name: Mapped[str | None] = mapped_column(String(120), default=None)
    major_name: Mapped[str | None] = mapped_column(String(120), default=None)
    min_score: Mapped[int | None] = mapped_column(Integer, default=None)
    min_rank: Mapped[int | None] = mapped_column(Integer, default=None)
    max_score: Mapped[int | None] = mapped_column(Integer, default=None)
    avg_score: Mapped[int | None] = mapped_column(Integer, default=None)
    actual_count: Mapped[int | None] = mapped_column(Integer, default=None)
    plan_count: Mapped[int | None] = mapped_column(Integer, default=None)
    required_subjects: Mapped[str | None] = mapped_column(String(120), default=None)
    source_url: Mapped[str] = mapped_column(String(500))
    published_at: Mapped[str | None] = mapped_column(String(20), default=None)              # 官方发布时间（从公告/URL解析）
    fetched_at: Mapped[str] = mapped_column(String(30))                                     # 抓取/导入时间 ISO8601
    content_sha256: Mapped[str] = mapped_column(String(64))                                 # 源文件哈希
    parser_version: Mapped[str] = mapped_column(String(30))
    doc_status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DataVersion(Base):
    """数据集版本台账：每个官方文件一行，附件哈希变化即视为官方修订。"""
    __tablename__ = 'data_versions'
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset: Mapped[str] = mapped_column(String(40), index=True)                            # 投档线 / 一分一段 / 招生计划 / 选科要求 / 高校名单
    province: Mapped[str | None] = mapped_column(String(20), default=None)
    exam_year: Mapped[int | None] = mapped_column(Integer, default=None)
    source_url: Mapped[str] = mapped_column(String(500))
    attachment_url: Mapped[str | None] = mapped_column(String(500), default=None)
    published_at: Mapped[str | None] = mapped_column(String(20), default=None)
    fetched_at: Mapped[str] = mapped_column(String(30))
    content_sha256: Mapped[str] = mapped_column(String(64))
    parser_version: Mapped[str] = mapped_column(String(30))
    doc_status: Mapped[str] = mapped_column(String(20))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    row_count: Mapped[int | None] = mapped_column(Integer, default=None)
    note: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MajorCatalog(Base):
    """专业卡：学什么 / 适合谁 / 难在哪 / 去哪里。内容自撰，标注来源与截止时间。"""
    __tablename__ = 'major_catalog'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    code: Mapped[str | None] = mapped_column(String(20), default=None)
    category: Mapped[str] = mapped_column(String(20))                                       # 13 门类
    major_class: Mapped[str | None] = mapped_column(String(40), default=None)
    study_what: Mapped[str] = mapped_column(String(200))
    fit_for: Mapped[str] = mapped_column(String(200))
    hard_where: Mapped[str] = mapped_column(String(200))
    career_where: Mapped[str] = mapped_column(String(200))
    riasec_main: Mapped[list | None] = mapped_column(JSON, default=None)
    riasec_secondary: Mapped[list | None] = mapped_column(JSON, default=None)
    source: Mapped[str] = mapped_column(String(120))
    as_of: Mapped[str] = mapped_column(String(20))


class EmploymentSummary(Base):
    """毕业去向摘要（人工摘录，必须带来源/年份/口径）。"""
    __tablename__ = 'employment_summaries'
    __table_args__ = (UniqueConstraint('university_id', 'year'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    university_id: Mapped[int] = mapped_column(ForeignKey('universities.id'), index=True)
    year: Mapped[int] = mapped_column(Integer)                                              # 届别，如 2025
    destination_rate: Mapped[float | None] = mapped_column(Float, default=None)             # 毕业去向落实率 %
    further_study_rate: Mapped[float | None] = mapped_column(Float, default=None)           # 升学率 %
    top_industries: Mapped[list | None] = mapped_column(JSON, default=None)
    top_regions: Mapped[list | None] = mapped_column(JSON, default=None)
    salary: Mapped[int | None] = mapped_column(Integer, default=None)                       # 月薪（元），可空
    key_employers: Mapped[list | None] = mapped_column(JSON, default=None)
    metric_definition: Mapped[str | None] = mapped_column(String(200), default=None)        # 口径说明
    source_url: Mapped[str] = mapped_column(String(500))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
