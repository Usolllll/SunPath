"""Real REST workflows against a disposable SQLite database, without touching .env or local user data."""
import csv
import io
import os
import secrets
import tempfile
import unittest
from pathlib import Path

temporary = tempfile.TemporaryDirectory(prefix='sunpath-test-')
os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(temporary.name) / 'test.db').as_posix()
os.environ['JWT_SECRET'] = secrets.token_urlsafe(48)
os.environ['DEMO_EMAIL'] = 'test-demo@sunpath.cn'
os.environ['DEMO_PASSWORD'] = 'TestOnly2026!'

from fastapi.testclient import TestClient
from app.main import app
from app.seed import seed
from app.core.database import engine, SessionLocal
from app.services.recommender import recommend, balanced_plan
from app.models.entities import Profile

PROFILE = {'province': '浙江', 'exam_year': 2026, 'score': 628, 'rank': 22580, 'subjects': ['物理', '化学', '生物'], 'regions': ['浙江', '江苏', '上海'], 'majors': ['计算机', '电子信息']}

class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()
        temporary.cleanup()

    def setUp(self):
        self.email = f'{secrets.token_hex(6)}@test.cn'
        response = self.client.post('/api/auth/register', json={'email': self.email, 'password': 'TestPassword123!', 'name': '测试同学'})
        self.assertEqual(response.status_code, 201, response.text)
        self.headers = {'Authorization': f"Bearer {response.json()['access_token']}"}

    def profile(self, **changes):
        response = self.client.put('/api/auth/profile', headers=self.headers, json={**PROFILE, **changes})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_auth_and_profile_validation(self):
        self.assertEqual(self.client.get('/api/catalog').status_code, 401)
        self.assertEqual(self.client.get('/api/recommendations', headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/auth/login', json={'email': self.email, 'password': 'WrongPassword'}).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/register', json={'email': self.email, 'password': 'TestPassword123!', 'name': '重复'}).status_code, 409)
        for change in [{'rank': 0}, {'score': 751}, {'subjects': ['物理', '物理', '化学']}, {'province': '不存在省份'}]:
            self.assertEqual(self.client.put('/api/auth/profile', headers=self.headers, json={**PROFILE, **change}).status_code, 422)
        result = self.profile()
        self.assertEqual(result['profile']['rank'], 22580)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.headers).json()['profile']['subjects'], PROFILE['subjects'])

    def test_recommendation_eligibility_and_same_province(self):
        self.profile()
        result = self.client.get('/api/recommendations', headers=self.headers).json()
        self.assertTrue(result['items'])
        self.assertTrue(all(result['counts'][risk] > 0 for risk in ['reach', 'steady', 'safe']))
        for item in result['items']:
            self.assertEqual(item['province'], '浙江')
            self.assertTrue(set(item['required_subjects']).issubset(PROFILE['subjects']))
            self.assertGreater(item['seats'], 0)
            self.assertEqual([h['year'] for h in item['history']], [2023, 2024, 2025])
            baseline = round(sum(h['rank'] * w for h, w in zip(item['history'], [1, 2, 3])) / 6)
            self.assertEqual(item['baseline_rank'], baseline)
            ratio = PROFILE['rank'] / baseline
            self.assertEqual(item['risk'], 'safe' if ratio <= .8 else 'steady' if ratio <= 1.08 else 'reach')
        first = result['items'][0]
        self.profile(province='广东')
        changed = self.client.get('/api/catalog/' + str(first['id']), headers=self.headers, params={'province': '广东'}).json()
        self.assertNotEqual(changed['latest_rank'], first['latest_rank'])
        self.profile(subjects=['历史', '政治', '地理'])
        humanities = self.client.get('/api/recommendations', headers=self.headers).json()['items']
        self.assertTrue(humanities)
        self.assertTrue(all(not x['required_subjects'] for x in humanities))

    def test_full_plan_save_reorder_snapshot_export(self):
        self.profile()
        generated = self.client.post('/api/recommendations/generate', headers=self.headers).json()
        items = generated['items']
        self.assertEqual(len(items), 12)
        self.assertEqual(generated['missing_tiers'], [])
        ids = [x['id'] for x in reversed(items)]
        response = self.client.post('/api/plans', headers=self.headers, json={'name': '计算机优先方案', 'group_ids': ids})
        self.assertEqual(response.status_code, 201, response.text)
        plan = response.json()
        self.assertEqual([x['id'] for x in plan['items']], ids)
        plan_id = plan['id']
        response = self.client.put(f'/api/plans/{plan_id}', headers=self.headers, json={'name': '调整方案', 'group_ids': ids[1:]})
        self.assertEqual(response.status_code, 200, response.text)
        csv_response = self.client.get(f'/api/plans/{plan_id}/export', headers=self.headers)
        self.assertEqual(csv_response.status_code, 200)
        rows = list(csv.reader(io.StringIO(csv_response.content.decode('utf-8-sig'))))
        self.assertEqual(rows[0][1], '调整方案')
        self.assertEqual(len(rows) - 4, 11)
        self.assertIn('模拟数据', csv_response.text)
        self.profile(rank=50000)
        saved = self.client.get(f'/api/plans/{plan_id}', headers=self.headers).json()
        self.assertEqual(saved['profile_snapshot']['rank'], 22580)
        self.assertEqual(self.client.get('/api/plans', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.delete(f'/api/plans/{plan_id}', headers=self.headers).status_code, 204)
        self.assertEqual(self.client.get(f'/api/plans/{plan_id}', headers=self.headers).status_code, 404)

    def test_plan_ownership_and_invalid_groups(self):
        self.profile()
        ids = [x['id'] for x in self.client.post('/api/recommendations/generate', headers=self.headers).json()['items']]
        for bad in [[], [999999], [ids[0], ids[0]]]:
            self.assertIn(self.client.post('/api/plans', headers=self.headers, json={'name': '无效', 'group_ids': bad}).status_code, [400, 422])
        pid = self.client.post('/api/plans', headers=self.headers, json={'name': '私有方案', 'group_ids': ids}).json()['id']
        other = self.client.post('/api/auth/login', json={'email': 'test-demo@sunpath.cn', 'password': 'TestOnly2026!'}).json()['access_token']
        other_headers = {'Authorization': f'Bearer {other}'}
        for method, path in [('get', f'/api/plans/{pid}'), ('get', f'/api/plans/{pid}/export'), ('delete', f'/api/plans/{pid}')]:
            self.assertEqual(getattr(self.client, method)(path, headers=other_headers).status_code, 404)
        self.assertEqual(self.client.put(f'/api/plans/{pid}', headers=other_headers, json={'name': '篡改', 'group_ids': ids}).status_code, 404)

    def test_logout_revokes_token_and_password_revokes_sessions(self):
        self.assertEqual(self.client.post('/api/auth/logout', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.headers).status_code, 401)
        token = self.client.post('/api/auth/login', json={'email': self.email, 'password': 'TestPassword123!'}).json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        self.assertEqual(self.client.put('/api/auth/password', headers=headers, json={'current_password': 'TestPassword123!', 'new_password': 'ChangedPassword123!'}).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me', headers=headers).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login', json={'email': self.email, 'password': 'ChangedPassword123!'}).status_code, 200)

    def test_catalog_filters_pagination_missing_year(self):
        response = self.client.get('/api/catalog', headers=self.headers, params={'q': '计算机', 'region': '浙江', 'page_size': 2}).json()
        self.assertEqual(len(response['items']), 2)
        self.assertTrue(all(x['university']['region'] == '浙江' and '计算机' in ' '.join(x['majors']) for x in response['items']))
        next_page = self.client.get('/api/catalog', headers=self.headers, params={'q': '计算机', 'region': '浙江', 'page_size': 2, 'page': 2}).json()
        self.assertNotEqual(response['items'][0]['id'], next_page['items'][0]['id'])
        self.assertEqual(self.client.get('/api/catalog', headers=self.headers, params={'province': '无效'}).status_code, 422)
        self.profile(exam_year=2027)
        self.assertEqual(self.client.get('/api/recommendations', headers=self.headers).json()['items'], [])
        generated = self.client.post('/api/recommendations/generate', headers=self.headers).json()
        self.assertEqual(generated['items'], [])
        self.assertEqual(len(generated['missing_tiers']), 3)

    def test_rule_boundaries_and_seed_idempotency(self):
        with SessionLocal() as db:
            for rank in [1, 2000000]:
                p = Profile(**{**PROFILE, 'rank': rank})
                result = recommend(db, p)
                if rank == 1:
                    self.assertTrue(result)
                    self.assertTrue(all(x['risk'] == 'safe' for x in result))
                else:
                    self.assertEqual(result, [])
                selected, missing = balanced_plan(result, 12)
                self.assertEqual(len({x['id'] for x in selected}), len(selected))
                self.assertIn('reach', missing)
        before = self.client.get('/api/overview', headers=self.headers).json()
        seed()
        after = self.client.get('/api/overview', headers=self.headers).json()
        self.assertEqual(before, after)
        self.assertEqual(after['groups'], 48)

if __name__ == '__main__':
    unittest.main()
