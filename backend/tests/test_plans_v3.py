"""v3 RTM-B：收藏 + 方案提交/撤回/批次/体检标记的隔离测试。

复用 test_workflow 的临时 SQLite 模式（先 `import test_workflow` 让它在导入 app 前设置
DATABASE_URL），绝不连接 backend/sunpath.db；体检标记用例用独立内存库，避免污染共享种子库。

运行（backend 目录下）：
    ..\\..\\Python311\\python.exe -m unittest tests.test_plans_v3 -v
"""
import secrets
import unittest

try:
    import test_workflow  # noqa: F401  先设置临时 DATABASE_URL，避免污染开发库
except ImportError:
    from tests import test_workflow  # noqa: F401

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models.entities import Admission, AuditLog, Enrollment, MajorGroup, Profile, University
from app.seed import seed
from app.services.enrichment import apply_university
from app.services.recommender import recommend

PROFILE = {'province': '浙江', 'exam_year': 2026, 'score': 628, 'rank': 22580,
           'subjects': ['物理', '化学', '生物'], 'regions': ['浙江', '江苏', '上海'],
           'majors': ['计算机', '电子信息']}


def new_account(client, name='测试同学'):
    email = f'{secrets.token_hex(8)}@test.cn'
    response = client.post('/api/auth/register', json={'email': email, 'password': 'TestPassword123!', 'name': name})
    assert response.status_code == 201, response.text
    return response.json()['user'], {'Authorization': f"Bearer {response.json()['access_token']}"}


def build_physical_database():
    """独立内存库：一个含「化学」专业组（色弱 red）、一个测控专业组（矫正视力 yellow）、一个无受限组。"""
    memory = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(memory)
    db = sessionmaker(bind=memory)()
    university = University(name='测试化工大学', city='杭州', region='浙江', level='省重点', category='理工类',
                            description='体检标记测试院校', initials='测化', color='#333333')
    apply_university(university)
    db.add(university)
    db.flush()

    def add_group(code, name, majors, required_subjects, baseline):
        group = MajorGroup(university_id=university.id, code=code, name=name, majors=majors,
                           required_subjects=required_subjects, tuition=6000)
        db.add(group)
        db.flush()
        for year in (2023, 2024, 2025):
            db.add(Admission(group_id=group.id, province='浙江', year=year, min_score=600, min_rank=baseline))
        db.add(Enrollment(group_id=group.id, province='浙江', year=2026, count=20))
        return group

    chemistry = add_group('001-01', '化学与化工专业组', ['化学工程与工艺', '应用化学'], ['物理', '化学'], 22000)
    instrument = add_group('001-02', '测控与仪器专业组', ['测控技术与仪器'], ['物理'], 23000)
    economics = add_group('001-03', '人文与经管专业组', ['经济学', '工商管理'], [], 24000)
    db.commit()
    return db, {'chemistry': chemistry.id, 'instrument': instrument.id, 'economics': economics.id}


class PlansV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()

    def setUp(self):
        self.user, self.headers = new_account(self.client)
        self.profile()

    # ---------------------------------------------------------------- helpers
    def profile(self, **changes):
        response = self.client.put('/api/auth/profile', headers=self.headers, json={**PROFILE, **changes})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def recommended_ids(self, count=4):
        response = self.client.get('/api/recommendations', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        ids = [item['id'] for item in response.json()['items']]
        self.assertGreaterEqual(len(ids), count)
        return ids[:count]

    def save_plan(self, name='测试方案', **extra):
        response = self.client.post('/api/plans', headers=self.headers,
                                    json={'name': name, 'group_ids': self.recommended_ids(), **extra})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def audit_actions(self, user_id):
        with SessionLocal() as db:
            return list(db.scalars(select(AuditLog.action).where(AuditLog.user_id == user_id)))

    def first_university_id(self, offset=0):
        with SessionLocal() as db:
            return db.scalars(select(University.id).order_by(University.id).offset(offset).limit(1)).one()

    # ---------------------------------------------------------------- 收藏
    def test_favorites_add_is_idempotent_and_audited(self):
        first_university = self.first_university_id(0)
        second_university = self.first_university_id(1)

        created = self.client.post('/api/favorites', headers=self.headers, json={'university_id': first_university})
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()['university']['id'], first_university)
        self.assertIn('created_at', created.json())

        duplicate = self.client.post('/api/favorites', headers=self.headers, json={'university_id': first_university})
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertEqual(duplicate.json()['id'], created.json()['id'])

        self.assertEqual(self.client.post('/api/favorites', headers=self.headers,
                                          json={'university_id': second_university}).status_code, 201)
        listing = self.client.get('/api/favorites', headers=self.headers)
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertEqual([item['university']['id'] for item in listing.json()], [second_university, first_university])
        self.assertEqual(set(listing.json()[0]['university']),
                         {'id', 'name', 'city', 'region', 'level', 'level_tier', 'category'})
        self.assertEqual(sorted(self.client.get('/api/favorites/ids', headers=self.headers).json()['ids']),
                         sorted([first_university, second_university]))

        self.assertIn('favorite.add', self.audit_actions(self.user['id']))
        self.assertEqual(self.client.get('/api/favorites').status_code, 401)
        self.assertEqual(self.client.post('/api/favorites', headers=self.headers,
                                          json={'university_id': 999999}).status_code, 404)
        self.assertEqual(self.client.post('/api/favorites', headers=self.headers,
                                          json={'university_id': 0}).status_code, 422)

    def test_favorites_delete_and_owner_isolation(self):
        university = self.first_university_id(0)
        other_user, other_headers = new_account(self.client, '另一账号')
        self.assertEqual(self.client.post('/api/favorites', headers=self.headers,
                                          json={'university_id': university}).status_code, 201)

        # 属主隔离：另一账号看不到、也删不掉、且不泄漏收藏是否存在之外的信息
        self.assertEqual(self.client.get('/api/favorites', headers=other_headers).json(), [])
        self.assertEqual(self.client.get('/api/favorites/ids', headers=other_headers).json(), {'ids': []})
        self.assertEqual(self.client.delete(f'/api/favorites/{university}', headers=other_headers).status_code, 404)
        self.assertEqual(len(self.client.get('/api/favorites', headers=self.headers).json()), 1)

        self.assertEqual(self.client.delete(f'/api/favorites/{university}', headers=self.headers).status_code, 204)
        self.assertEqual(self.client.delete(f'/api/favorites/{university}', headers=self.headers).status_code, 404)
        self.assertEqual(self.client.get('/api/favorites', headers=self.headers).json(), [])
        self.assertEqual(self.client.get('/api/favorites/ids', headers=self.headers).json(), {'ids': []})
        self.assertIn('favorite.remove', self.audit_actions(self.user['id']))
        self.assertNotIn('favorite.add', self.audit_actions(other_user['id']))

    # ---------------------------------------------------------------- 方案批次
    def test_plan_batch_default_and_validation(self):
        default = self.save_plan('默认批次方案')
        self.assertEqual(default['batch'], '本科批')
        self.assertEqual(default['status'], 'draft')
        self.assertIsNone(default['submitted_at'])
        self.assertIsNone(default['idempotency_key'])
        self.assertEqual(default['profile_snapshot']['province'], '浙江')

        special = self.save_plan('专科批次方案', batch='专科批')
        self.assertEqual(special['batch'], '专科批')
        self.assertEqual([plan['batch'] for plan in self.client.get('/api/plans', headers=self.headers).json()],
                         ['专科批', '本科批'])

        self.assertEqual(self.client.post('/api/plans', headers=self.headers,
                                          json={'name': '非法批次', 'group_ids': self.recommended_ids(), 'batch': '提前批'}).status_code, 422)
        self.assertEqual(self.client.post('/api/plans', headers=self.headers,
                                          json={'name': '非法批次', 'group_ids': self.recommended_ids(), 'batch': None}).status_code, 422)

    # ---------------------------------------------------------------- 提交/删除只读
    def test_submitted_plan_cannot_be_edited_or_deleted(self):
        plan = self.save_plan('待提交方案')
        submitted = self.client.post(f"/api/plans/{plan['id']}/submit", headers=self.headers)
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(submitted.json()['status'], 'submitted')
        self.assertIsNotNone(submitted.json()['submitted_at'])

        changed = {'name': '偷偷改名', 'group_ids': [item['id'] for item in plan['items']]}
        blocked_put = self.client.put(f"/api/plans/{plan['id']}", headers=self.headers, json=changed)
        self.assertEqual(blocked_put.status_code, 409, blocked_put.text)
        self.assertIn('已提交', blocked_put.json()['detail'])
        self.assertEqual(self.client.delete(f"/api/plans/{plan['id']}", headers=self.headers).status_code, 409)

        kept = self.client.get(f"/api/plans/{plan['id']}", headers=self.headers).json()
        self.assertEqual(kept['name'], '待提交方案')
        self.assertEqual(kept['status'], 'submitted')
        self.assertEqual([item['id'] for item in kept['items']], [item['id'] for item in plan['items']])
        # 已提交方案仍可导出（导出属于只读操作）
        self.assertEqual(self.client.get(f"/api/plans/{plan['id']}/export", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/api/plans', headers=self.headers).json()[0]['status'], 'submitted')

    # ---------------------------------------------------------------- 提交重校验
    def test_submit_revalidates_items_against_current_profile(self):
        plan = self.save_plan('提交前重校验')
        self.profile(subjects=['历史', '政治', '地理'])  # 原方案都是要求物理+化学的理工组
        rejected = self.client.post(f"/api/plans/{plan['id']}/submit", headers=self.headers)
        self.assertEqual(rejected.status_code, 400, rejected.text)
        self.assertEqual(self.client.get(f"/api/plans/{plan['id']}", headers=self.headers).json()['status'],
                         'draft')
        self.assertEqual(self.client.post(f"/api/plans/{plan['id']}/withdraw", headers=self.headers).status_code, 400)

    def test_withdraw_restores_editable_draft(self):
        plan = self.save_plan('可撤回方案')
        self.assertEqual(self.client.post(f"/api/plans/{plan['id']}/submit", headers=self.headers).status_code, 200)
        withdrawn = self.client.post(f"/api/plans/{plan['id']}/withdraw", headers=self.headers)
        self.assertEqual(withdrawn.status_code, 200, withdrawn.text)
        self.assertEqual(withdrawn.json()['status'], 'draft')
        self.assertIsNone(withdrawn.json()['submitted_at'])
        self.assertEqual(self.client.post(f"/api/plans/{plan['id']}/withdraw", headers=self.headers).status_code, 400)

        editable = self.client.put(f"/api/plans/{plan['id']}", headers=self.headers,
                                   json={'name': '撤回后改名', 'group_ids': self.recommended_ids()})
        self.assertEqual(editable.status_code, 200, editable.text)
        self.assertEqual(editable.json()['name'], '撤回后改名')
        self.assertEqual(self.client.delete(f"/api/plans/{plan['id']}", headers=self.headers).status_code, 204)
        self.assertEqual(self.client.get(f"/api/plans/{plan['id']}", headers=self.headers).status_code, 404)

    def test_repeat_submit_is_idempotent(self):
        plan = self.save_plan('重复提交方案')
        first = self.client.post(f"/api/plans/{plan['id']}/submit", headers=self.headers)
        second = self.client.post(f"/api/plans/{plan['id']}/submit", headers=self.headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(self.audit_actions(self.user['id']).count('plan.submit'), 1)

    # ---------------------------------------------------------------- Idempotency-Key
    def test_create_idempotency_key_dedupes_and_is_user_scoped(self):
        ids = self.recommended_ids()
        key = secrets.token_hex(8)
        headers = {**self.headers, 'Idempotency-Key': key}
        first = self.client.post('/api/plans', headers=headers, json={'name': '幂等方案', 'group_ids': ids})
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json()['idempotency_key'], key)

        replay = self.client.post('/api/plans', headers=headers,
                                  json={'name': '重复请求不该新建', 'group_ids': ids[:2]})
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json()['id'], first.json()['id'])
        self.assertEqual(replay.json()['name'], '幂等方案')
        self.assertEqual(len(self.client.get('/api/plans', headers=self.headers).json()), 1)

        other_key = self.client.post('/api/plans', headers={**self.headers, 'Idempotency-Key': secrets.token_hex(8)},
                                     json={'name': '另一个 key', 'group_ids': ids})
        self.assertEqual(other_key.status_code, 201)
        self.assertNotEqual(other_key.json()['id'], first.json()['id'])

        # key 作用域是同一用户：另一账号用同一 key 仍会新建自己的方案
        other_user, other_headers = new_account(self.client, '另一账号')
        self.client.put('/api/auth/profile', headers=other_headers, json=PROFILE)
        other_ids = [item['id'] for item in self.client.get('/api/recommendations', headers=other_headers).json()['items'][:2]]
        other = self.client.post('/api/plans', headers={**other_headers, 'Idempotency-Key': key},
                                 json={'name': '另一账号同 key', 'group_ids': other_ids})
        self.assertEqual(other.status_code, 201, other.text)
        self.assertNotEqual(other.json()['id'], first.json()['id'])
        self.assertEqual(len(self.client.get('/api/plans', headers=self.headers).json()), 2)

        # 非法 key 长度 → 422
        self.assertEqual(self.client.post('/api/plans', headers={**self.headers, 'Idempotency-Key': ''},
                                          json={'name': '空 key', 'group_ids': ids}).status_code, 422)
        self.assertEqual(self.client.post('/api/plans', headers={**self.headers, 'Idempotency-Key': 'x' * 65},
                                          json={'name': '过长 key', 'group_ids': ids}).status_code, 422)

    # ---------------------------------------------------------------- 审计
    def test_plan_export_writes_audit(self):
        plan = self.save_plan('导出审计方案')
        self.assertIn('plan.create', self.audit_actions(self.user['id']))
        exported = self.client.get(f"/api/plans/{plan['id']}/export", headers=self.headers)
        self.assertEqual(exported.status_code, 200)
        self.assertIn('attachment', exported.headers['content-disposition'])
        actions = self.audit_actions(self.user['id'])
        self.assertIn('plan.export', actions)
        self.assertEqual(actions.count('plan.export'), 1)
        # 更新/删除也写审计
        self.client.put(f"/api/plans/{plan['id']}", headers=self.headers,
                        json={'name': '导出前改名', 'group_ids': self.recommended_ids()})
        self.client.delete(f"/api/plans/{plan['id']}", headers=self.headers)
        actions = self.audit_actions(self.user['id'])
        self.assertIn('plan.update', actions)
        self.assertIn('plan.delete', actions)

    # ---------------------------------------------------------------- 体检标记
    def test_physical_flags_hint_without_changing_pool(self):
        db, groups = build_physical_database()
        try:
            weak_profile = Profile(**PROFILE, physical={'color_weak': True, 'corrected_vision': 500})
            plain_profile = Profile(**PROFILE)
            weak_pool = recommend(db, weak_profile)
            plain_pool = recommend(db, plain_profile)
            self.assertTrue(weak_pool)

            # 不改变候选池、顺序与风险/位次：只在 item 上多一个提示字段
            self.assertEqual([item['id'] for item in weak_pool], [item['id'] for item in plain_pool])
            self.assertEqual([(item['id'], item['risk'], item['rank_ratio']) for item in weak_pool],
                             [(item['id'], item['risk'], item['rank_ratio']) for item in plain_pool])

            by_id = {item['id']: item for item in weak_pool}
            chemistry = by_id[groups['chemistry']]
            self.assertTrue(chemistry['physical_flags'])
            self.assertIn({'level': 'red', 'label': '色弱'}, [{'level': flag['level'], 'label': flag['label']}
                                                             for flag in chemistry['physical_flags']])
            self.assertIn('化学工程与工艺', ' '.join(flag['text'] for flag in chemistry['physical_flags']))

            instrument = by_id[groups['instrument']]
            self.assertTrue(instrument['physical_flags'])
            self.assertTrue(all(flag['level'] == 'yellow' for flag in instrument['physical_flags']))

            self.assertEqual(by_id[groups['economics']]['physical_flags'], [])

            # 无体检数据 → 全部为空数组
            self.assertTrue(all(item['physical_flags'] == [] for item in plain_pool))
            # 体检提示不写入理由/风险排序字段（不构成录取结论）
            self.assertTrue(all('physical_flags' in item for item in plain_pool))
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
