"""Create tables and deterministic mock data. Idempotent; never overwrites user data."""
from sqlalchemy import select
from app.core.database import Base, engine, SessionLocal
from app.core.config import get_settings
from app.core.security import hash_password
from app.models.entities import User, Profile, University, MajorGroup, Admission, Enrollment
from app.schemas.dto import PROVINCES

SCHOOLS = [
    ('浙江大学', '杭州', '浙江', '985 / 211 / 双一流', '综合类', '浙大', '#326766', 4200),
    ('上海交通大学', '上海', '上海', '985 / 211 / 双一流', '综合类', '交大', '#a54a50', 2200),
    ('复旦大学', '上海', '上海', '985 / 211 / 双一流', '综合类', '复旦', '#35618a', 1800),
    ('南京大学', '南京', '江苏', '985 / 211 / 双一流', '综合类', '南大', '#735091', 3500),
    ('同济大学', '上海', '上海', '985 / 211 / 双一流', '理工类', '同济', '#3b7491', 7800),
    ('东南大学', '南京', '江苏', '985 / 211 / 双一流', '综合类', '东南', '#4f7968', 10200),
    ('华东师范大学', '上海', '上海', '985 / 211 / 双一流', '师范类', '华师', '#a85b64', 11500),
    ('华东理工大学', '上海', '上海', '211 / 双一流', '理工类', '华理', '#3f708a', 16800),
    ('南京理工大学', '南京', '江苏', '211 / 双一流', '理工类', '南理', '#6b6297', 18200),
    ('苏州大学', '苏州', '江苏', '211 / 双一流', '综合类', '苏大', '#a25d57', 21000),
    ('杭州电子科技大学', '杭州', '浙江', '省重点', '理工类', '杭电', '#397b96', 25500),
    ('浙江工业大学', '杭州', '浙江', '省重点', '理工类', '浙工', '#327d79', 29000),
    ('南京邮电大学', '南京', '江苏', '双一流', '理工类', '南邮', '#4976a1', 23500),
    ('合肥工业大学', '合肥', '安徽', '211 / 双一流', '理工类', '合工', '#a06b46', 31000),
    ('宁波大学', '宁波', '浙江', '双一流', '综合类', '宁大', '#557a94', 37000),
    ('浙江理工大学', '杭州', '浙江', '省重点', '理工类', '浙理', '#8b5c80', 44000),
    ('温州大学', '温州', '浙江', '省重点', '综合类', '温大', '#64846c', 61000),
    ('中国计量大学', '杭州', '浙江', '省重点', '理工类', '计量', '#517e9c', 52000),
    ('四川大学', '成都', '四川', '985 / 211 / 双一流', '综合类', '川大', '#9d5d52', 13000),
    ('电子科技大学', '成都', '四川', '985 / 211 / 双一流', '理工类', '成电', '#3d6793', 9200),
    ('武汉理工大学', '武汉', '湖北', '211 / 双一流', '理工类', '武理', '#568481', 26500),
    ('深圳大学', '深圳', '广东', '省重点', '综合类', '深大', '#8a496c', 33000),
    ('广东工业大学', '广州', '广东', '省重点', '理工类', '广工', '#627b99', 57000),
    ('浙江工商大学', '杭州', '浙江', '省重点', '财经类', '浙商', '#94784e', 48000),
]

def seed():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for index, (name, city, region, level, category, initials, color, base_rank) in enumerate(SCHOOLS):
            if db.scalar(select(University).where(University.name == name)):
                continue
            university = University(name=name, city=city, region=region, level=level, category=category, initials=initials, color=color,
                                    description=f'{name}位于{city}。本原型提供该校两个模拟专业组，用于演示院校探索、选科匹配与志愿规划；不代表该校实际招生信息。')
            db.add(university)
            db.flush()
            for offset in range(2):
                science = offset == 0
                majors = (['计算机科学与技术', '软件工程', '人工智能'] if index % 3 else ['电子信息工程', '通信工程', '自动化']) if science else ['经济学', '工商管理', '新闻传播学']
                group = MajorGroup(university_id=university.id, code=f'{index + 1:03d}-{offset + 1:02d}', name='理工与信息专业组' if science else '人文与经管专业组', majors=majors, required_subjects=['物理', '化学'] if science else [], tuition=6000 if science else 5300)
                db.add(group)
                db.flush()
                for pi, province in enumerate(PROVINCES):
                    local_rank = int(base_rank * (1 + pi * .13) * (1 if science else 1.22))
                    for yi, year in enumerate([2023, 2024, 2025]):
                        factor = [1.08, .96, 1.0][yi] + ((index % 5) - 2) * .012
                        rank = max(100, round(local_rank * factor))
                        score = max(440, min(710, round(708 - (rank ** .49) * .48 - pi * 2 + yi)))
                        db.add(Admission(group_id=group.id, province=province, year=year, min_score=score, min_rank=rank))
                    db.add(Enrollment(group_id=group.id, province=province, year=2026, count=12 + (index * 7 + offset * 3 + pi) % 48))
        settings = get_settings()
        if settings.demo_email and settings.demo_password and not db.scalar(select(User).where(User.email == settings.demo_email.lower())):
            if len(settings.demo_password) < 8:
                raise ValueError('DEMO_PASSWORD 至少 8 位')
            user = User(email=settings.demo_email.lower(), name='林同学', password_hash=hash_password(settings.demo_password))
            user.profile = Profile(province='浙江', exam_year=2026, score=628, rank=22580, subjects=['物理', '化学', '生物'], regions=['浙江', '上海', '江苏'], majors=['计算机', '电子信息'])
            db.add(user)
        db.commit()
    print('Initialized: 24 universities, 48 groups, 864 admission records, 288 enrollment records. All simulated.')

if __name__ == '__main__':
    seed()
