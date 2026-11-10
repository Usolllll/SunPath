"""v2 取舍沙盘打分/对比的单元测试（独立内存 SQLite，不依赖 .env 或开发库）。"""
import unittest
from collections import Counter

# 先导入 test_workflow：它在导入 app 之前设置临时 DATABASE_URL，
# 避免本模块先导入 app.core.database 把引擎绑到开发库（unittest discover 顺序问题）。
try:
    import test_workflow  # noqa: F401
except ImportError:  # 直接运行 tests.test_scoring 时
    from tests import test_workflow  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import Admission, Enrollment, MajorGroup, Profile, University
from app.services import budget, scoring
from app.services.recommender import balanced_plan, recommend

# (院校, 城市, 地区, 层次, 类型, 三年参考位次, 专业组方向)
SCHOOLS = [
    ('浙江大学', '杭州', '浙江', '985 / 211 / 双一流', '综合类', 17000, 'science'),
    ('上海交通大学', '上海', '上海', '985 / 211 / 双一流', '综合类', 18000, 'humanities'),
    ('南京大学', '南京', '江苏', '985 / 211 / 双一流', '综合类', 19000, 'science'),
    ('南京邮电大学', '南京', '江苏', '双一流', '理工类', 20000, 'science'),
    ('杭州电子科技大学', '杭州', '浙江', '省重点', '理工类', 22500, 'science'),
    ('浙江工业大学', '杭州', '浙江', '省重点', '理工类', 23000, 'humanities'),
    ('苏州大学', '苏州', '江苏', '211 / 双一流', '综合类', 24000, 'science'),
    ('宁波大学', '宁波', '浙江', '双一流', '综合类', 25000, 'humanities'),
    ('温州大学', '温州', '浙江', '省重点', '综合类', 28000, 'science'),
    ('浙江理工大学', '杭州', '浙江', '省重点', '理工类', 32000, 'science'),
    ('中国计量大学', '杭州', '浙江', '省重点', '理工类', 35000, 'science'),
    ('浙江工商大学', '杭州', '浙江', '省重点', '财经类', 40000, 'humanities'),
]
SCIENCE_MAJORS = ['计算机科学与技术', '软件工程', '人工智能']
HUMANITIES_MAJORS = ['经济学', '工商管理']

PROFILE = dict(province='浙江', exam_year=2026, score=628, rank=22580,
               subjects=['物理', '化学', '生物'], regions=['浙江', '江苏', '上海'],
               majors=['计算机', '电子信息'], interests=None, budget_total=None, priority_mode='balanced')


def build_database():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    for index, (name, city, region, level, category, baseline, direction) in enumerate(SCHOOLS):
        university = University(name=name, city=city, region=region, level=level, category=category,
                                description=f'{name}测试数据', initials=name[:2], color='#333333')
        from app.services.enrichment import apply_university
        apply_university(university)
        session.add(university)
        session.flush()
        majors = SCIENCE_MAJORS if direction == 'science' else HUMANITIES_MAJORS
        group = MajorGroup(university_id=university.id, code=f'{index + 1:03d}-01',
                           name='理工与信息专业组' if direction == 'science' else '人文与经管专业组',
                           majors=majors,
                           required_subjects=['物理', '化学'] if direction == 'science' else [],
                           tuition=6000 if direction == 'science' else 5300,
                           tuition_type='公办', accommodation=1000, duration_years=4, cost_year=2026)
        session.add(group)
        session.flush()
        for year in (2023, 2024, 2025):
            session.add(Admission(group_id=group.id, province='浙江', year=year,
                                  min_score=600, min_rank=baseline))
        session.add(Enrollment(group_id=group.id, province='浙江', year=2026, count=30))
    session.commit()
    return session


def make_profile(**changes):
    values = dict(PROFILE)
    values.update(changes)
    return Profile(**values)


class ScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = build_database()
        cls.profile = make_profile()
        cls.pool_legacy = recommend(cls.db, cls.profile, mode=None)
        cls.pools = {mode: recommend(cls.db, cls.profile, mode=mode) for mode in ('school', 'balanced', 'major')}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_three_modes_keep_same_pool_and_quota(self):
        legacy_ids = {item['id'] for item in self.pool_legacy}
        for mode, pool in self.pools.items():
            self.assertEqual({item['id'] for item in pool}, legacy_ids, mode)
        plans = {mode: balanced_plan(pool, 3) for mode, pool in self.pools.items()}
        for mode, (items, _missing) in plans.items():
            self.assertEqual(len(items), 3, mode)
        self.assertEqual(Counter(item['risk'] for item in plans['school'][0]),
                         Counter(item['risk'] for item in plans['major'][0]))
        self.assertEqual(Counter(item['risk'] for item in plans['school'][0]),
                         Counter(item['risk'] for item in balanced_plan(self.pool_legacy, 3)[0]))

    def test_school_vs_major_monotonic(self):
        plans = {mode: balanced_plan(pool, 6)[0] for mode, pool in self.pools.items()}
        mean = lambda items, key: sum(item[key] for item in items) / len(items)
        self.assertGreater(mean(plans['school'], 'school_score'), mean(plans['major'], 'school_score'))
        self.assertLess(mean(plans['school'], 'major_score'), mean(plans['major'], 'major_score'))

    def test_scores_and_handedness_are_bounded(self):
        for item in self.pools['balanced']:
            self.assertGreaterEqual(item['school_score'], 0)
            self.assertLessEqual(item['school_score'], 100)
            self.assertGreaterEqual(item['major_score'], 0)
            self.assertLessEqual(item['major_score'], 100)
            self.assertGreaterEqual(item['rank_fit'], 0)
            self.assertLessEqual(item['rank_fit'], 100)
            self.assertEqual(set(item['weights']), {'school', 'major', 'fit'})

    def test_compare_diff_self_consistent(self):
        a = balanced_plan(self.pools['school'], 6)[0]
        b = balanced_plan(self.pools['major'], 6)[0]
        diff = scoring.diff_plans(a, b)
        a_ids = [item['id'] for item in a]
        b_ids = [item['id'] for item in b]
        self.assertEqual(diff['a_count'], 6)
        self.assertEqual(diff['b_count'], 6)
        self.assertEqual(diff['changed'], sum(1 for x, y in zip(a_ids, b_ids) if x != y))
        union = set(a_ids) | set(b_ids)
        self.assertEqual(set(diff['added']) | set(diff['removed']) | (set(a_ids) & set(b_ids)), union)
        self.assertEqual(len(diff['rank_delta']), len(set(a_ids) & set(b_ids)))
        self.assertIn('院校层次平均', scoring.summarize(diff))

    def test_legacy_mode_keeps_v1_ordering(self):
        keys = [(-item['preference_matches'], abs(item['rank_ratio'] - 0.95), item['id']) for item in self.pool_legacy]
        self.assertEqual(keys, sorted(keys))

    def test_interests_change_major_score(self):
        it_profile = make_profile(interests={'R': 20, 'I': 95, 'A': 30, 'S': 40, 'E': 50, 'C': 70})
        pool = recommend(self.db, it_profile, mode='major')
        science = [item for item in pool if item['major_score'] > 0]
        self.assertTrue(science)
        self.assertEqual(pool[0]['risk'] in ('reach', 'steady', 'safe'), True)

    def test_budget_cost_and_cap(self):
        item = next(i for i in self.pools['balanced'] if i.get('cost'))
        cost = item['cost']
        self.assertEqual(cost['total'], (cost['tuition'] + cost['accommodation'] + cost['living']) * cost['years'])
        self.assertGreater(cost['living'], 0)
        capped = recommend(self.db, make_profile(budget_total=90000), mode='balanced', budget_cap=100000)
        self.assertTrue(capped)
        self.assertTrue(all(i['cost']['total'] <= 100000 for i in capped))
        summary = budget.budget_summary(capped, 100000)
        self.assertEqual(summary['over_budget'], 0)
        self.assertEqual(summary['count'], len(capped))


if __name__ == '__main__':
    unittest.main()
