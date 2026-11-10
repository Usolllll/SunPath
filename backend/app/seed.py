"""Create tables and deterministic mock data. Idempotent; never overwrites user data."""
from sqlalchemy import select, func
from app.core.database import Base, engine, SessionLocal
from app.core.config import get_settings
from app.core.security import hash_password
from app.models.entities import User, Profile, University, MajorGroup, Admission, Enrollment, MajorCatalog
from app.services.enrichment import apply_group, apply_university, major_cards
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
    ('北京大学', '北京', '北京', '985 / 211 / 双一流', '综合类', '北大', '#9e4753', 500),
    ('清华大学', '北京', '北京', '985 / 211 / 双一流', '理工类', '清华', '#78518c', 400),
    ('中国人民大学', '北京', '北京', '985 / 211 / 双一流', '综合类', '人大', '#a25b55', 3000),
    ('北京航空航天大学', '北京', '北京', '985 / 211 / 双一流', '理工类', '北航', '#426c98', 6000),
    ('北京理工大学', '北京', '北京', '985 / 211 / 双一流', '理工类', '北理', '#5a8569', 8500),
    ('北京师范大学', '北京', '北京', '985 / 211 / 双一流', '师范类', '北师', '#556f9b', 10500),
    ('南开大学', '天津', '天津', '985 / 211 / 双一流', '综合类', '南开', '#84548e', 9000),
    ('天津大学', '天津', '天津', '985 / 211 / 双一流', '理工类', '天大', '#47799a', 11000),
    ('山东大学', '济南', '山东', '985 / 211 / 双一流', '综合类', '山大', '#a3545f', 14000),
    ('中国海洋大学', '青岛', '山东', '985 / 211 / 双一流', '综合类', '海大', '#46829b', 19000),
    ('武汉大学', '武汉', '湖北', '985 / 211 / 双一流', '综合类', '武大', '#4c8376', 7000),
    ('华中科技大学', '武汉', '湖北', '985 / 211 / 双一流', '综合类', '华科', '#587795', 6500),
    ('中南大学', '长沙', '湖南', '985 / 211 / 双一流', '综合类', '中南', '#5b79a2', 17000),
    ('湖南大学', '长沙', '湖南', '985 / 211 / 双一流', '综合类', '湖大', '#a26e56', 18000),
    ('中山大学', '广州', '广东', '985 / 211 / 双一流', '综合类', '中大', '#4f846a', 12000),
    ('华南理工大学', '广州', '广东', '985 / 211 / 双一流', '理工类', '华工', '#9d6d54', 13500),
    ('厦门大学', '厦门', '福建', '985 / 211 / 双一流', '综合类', '厦大', '#487d9c', 12500),
    ('西安交通大学', '西安', '陕西', '985 / 211 / 双一流', '综合类', '西交', '#596f9b', 7200),
    ('西北工业大学', '西安', '陕西', '985 / 211 / 双一流', '理工类', '西工', '#6486a2', 9500),
    ('重庆大学', '重庆', '重庆', '985 / 211 / 双一流', '综合类', '重大', '#5a7e94', 19500),
    ('西南大学', '重庆', '重庆', '211 / 双一流', '综合类', '西南', '#6a8a71', 24000),
    ('东北大学', '沈阳', '辽宁', '985 / 211 / 双一流', '理工类', '东北', '#5b7e9c', 22000),
    ('大连理工大学', '大连', '辽宁', '985 / 211 / 双一流', '理工类', '大工', '#477696', 15500),
    ('吉林大学', '长春', '吉林', '985 / 211 / 双一流', '综合类', '吉大', '#4f7c9d', 16500),
    ('哈尔滨工业大学', '哈尔滨', '黑龙江', '985 / 211 / 双一流', '理工类', '哈工', '#576b91', 8000),
    ('哈尔滨工程大学', '哈尔滨', '黑龙江', '211 / 双一流', '理工类', '哈工程', '#497e96', 23000),
    ('兰州大学', '兰州', '甘肃', '985 / 211 / 双一流', '综合类', '兰大', '#5e7e99', 27000),
    ('郑州大学', '郑州', '河南', '211 / 双一流', '综合类', '郑大', '#607d9d', 32000),
    ('西安电子科技大学', '西安', '陕西', '211 / 双一流', '理工类', '西电', '#9a5b65', 17500),
    ('北京邮电大学', '北京', '北京', '211 / 双一流', '理工类', '北邮', '#4d7c9c', 15000),
    ('上海大学', '上海', '上海', '211 / 双一流', '综合类', '上大', '#6578a4', 26000),
    ('东华大学', '上海', '上海', '211 / 双一流', '理工类', '东华', '#8f639a', 28500),
    ('南京航空航天大学', '南京', '江苏', '211 / 双一流', '理工类', '南航', '#4a7c9e', 20000),
    ('河海大学', '南京', '江苏', '211 / 双一流', '理工类', '河海', '#4f8195', 34000),
    ('福州大学', '福州', '福建', '211 / 双一流', '理工类', '福大', '#637e9c', 40000),
    ('南昌大学', '南昌', '江西', '211 / 双一流', '综合类', '昌大', '#8b656d', 46000),
]

def seed():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for index, (name, city, region, level, category, initials, color, base_rank) in enumerate(SCHOOLS):
            if db.scalar(select(University).where(University.name == name)):
                continue
            university = University(name=name, city=city, region=region, level=level, category=category, initials=initials, color=color,
                                    description=f'{name}位于{city}。本原型提供该校两个模拟专业组，用于演示院校探索、选科匹配与志愿规划；不代表该校实际招生信息。')
            apply_university(university)
            db.add(university)
            db.flush()
            for offset in range(2):
                science = offset == 0
                majors = (['计算机科学与技术', '软件工程', '人工智能'] if index % 3 else ['电子信息工程', '通信工程', '自动化']) if science else ['经济学', '工商管理', '新闻传播学']
                group = MajorGroup(university_id=university.id, code=f'{index + 1:03d}-{offset + 1:02d}', name='理工与信息专业组' if science else '人文与经管专业组', majors=majors, required_subjects=['物理', '化学'] if science else [], tuition=6000 if science else 5300)
                apply_group(group)
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
        for name, card in major_cards().items():
            if db.scalar(select(MajorCatalog).where(MajorCatalog.name == name)):
                continue
            db.add(MajorCatalog(
                name=name, code=card.get('code'), category=card['category'], major_class=card.get('major_class'),
                study_what=card['study_what'], fit_for=card['fit_for'], hard_where=card['hard_where'],
                career_where=card['career_where'], riasec_main=card.get('riasec_main'),
                riasec_secondary=card.get('riasec_secondary'), source=card.get('source', '自撰摘要'), as_of=card.get('as_of', '2026-11'),
            ))
        settings = get_settings()
        if settings.demo_email and settings.demo_password and not db.scalar(select(User).where(User.email == settings.demo_email.lower())):
            if len(settings.demo_password) < 8:
                raise ValueError('DEMO_PASSWORD 至少 8 位')
            user = User(email=settings.demo_email.lower(), name='林同学', password_hash=hash_password(settings.demo_password))
            user.profile = Profile(province='浙江', exam_year=2026, score=628, rank=22580, subjects=['物理', '化学', '生物'], regions=['浙江', '上海', '江苏'], majors=['计算机', '电子信息'])
            db.add(user)
        db.commit()
        counts = [db.scalar(select(func.count()).select_from(model)) for model in (University, MajorGroup, Admission, Enrollment, MajorCatalog)]
    print(f'Initialized: {counts[0]} universities, {counts[1]} groups, {counts[2]} admission records, {counts[3]} enrollment records, {counts[4]} major cards. All admission data simulated.')

if __name__ == '__main__':
    seed()
