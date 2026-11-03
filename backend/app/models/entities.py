from datetime import datetime, timezone
from sqlalchemy import String, Integer, ForeignKey, JSON, DateTime, UniqueConstraint
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
