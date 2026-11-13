"""v3 增量功能测试：招生计划年度对比（M4-03）与加分/专项资格登记（M2-04）。

复用 test_workflow 的临时 SQLite 模式，不连开发库。
"""
import os
import secrets
import unittest
from pathlib import Path

try:
    import test_workflow  # noqa: F401  先设置临时 DATABASE_URL
except ImportError:
    from tests import test_workflow  # noqa: F401

from fastapi.testclient import TestClient

from app.core.database import engine
from app.main import app
from app.seed import seed

PROFILE = {
    'province': '浙江', 'exam_year': 2026, 'score': 628, 'rank': 22580,
    'subjects': ['物理', '化学', '生物'], 'regions': ['浙江', '江苏', '上海'],
    'majors': ['计算机', '电子信息'], 'priority_mode': 'major',
    'interests': {'R': 40, 'I': 80, 'A': 30, 'S': 50, 'E': 40, 'C': 60},
    'budget_total': 150000, 'physical': {'color_weak': False},
    'bonus_points': 5, 'bonus_type': 'minority', 'special_programs': ['国家专项'],
}


class V3AssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 其他测试类可能已清理临时目录：确保目录存在再建表
        url = os.environ.get('DATABASE_URL', '')
        if url.startswith('sqlite:///'):
            Path(url[len('sqlite:///'):]).parent.mkdir(parents=True, exist_ok=True)
        seed()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()

    def setUp(self):
        email = f'{secrets.token_hex(6)}@v3-test.cn'
        response = self.client.post('/api/auth/register',
                                    json={'email': email, 'password': 'V3TestPassword123!', 'name': '增量测试'})
        self.assertEqual(response.status_code, 201, response.text)
        self.email = email
        self.headers = {'Authorization': f"Bearer {response.json()['access_token']}"}

    def save_profile(self, **changes):
        return self.client.put('/api/auth/profile', headers=self.headers,
                               json={**PROFILE, **changes})

    def test_bonus_and_special_programs_roundtrip_and_validation(self):
        response = self.save_profile()
        self.assertEqual(response.status_code, 200, response.text)
        profile = response.json()['profile']
        self.assertEqual(profile['bonus_points'], 5)
        self.assertEqual(profile['bonus_type'], 'minority')
        self.assertEqual(profile['special_programs'], ['国家专项'])

        reread = self.client.get('/api/auth/me', headers=self.headers)
        self.assertEqual(reread.status_code, 200, reread.text)
        self.assertEqual(reread.json()['profile']['bonus_points'], 5)

        # 范围与枚举校验：加分 0–20、专项资格固定三类
        self.assertEqual(self.save_profile(bonus_points=21).status_code, 422)
        self.assertEqual(self.save_profile(bonus_points=-1).status_code, 422)
        self.assertEqual(self.save_profile(bonus_type='unknown').status_code, 422)
        self.assertEqual(self.save_profile(special_programs=['不存在的专项']).status_code, 422)
        # 重复专项自动去重
        deduped = self.save_profile(special_programs=['国家专项', '国家专项']).json()['profile']
        self.assertEqual(deduped['special_programs'], ['国家专项'])

        # 方案快照保留加分与专项资格（只登记，不改变位次）
        recommendations = self.client.get('/api/recommendations', headers=self.headers)
        self.assertEqual(recommendations.status_code, 200, recommendations.text)
        group_ids = [item['id'] for item in recommendations.json()['items'][:3]]
        plan = self.client.post('/api/plans', headers=self.headers,
                                json={'name': '加分快照测试', 'group_ids': group_ids, 'batch': '本科批'})
        self.assertEqual(plan.status_code, 201, plan.text)
        snapshot = plan.json()['profile_snapshot']
        self.assertEqual(snapshot['bonus_points'], 5)
        self.assertEqual(snapshot['special_programs'], ['国家专项'])
        self.assertEqual(snapshot['rank'], 22580)

    def test_plan_trend_in_group_detail(self):
        catalog = self.client.get('/api/catalog', headers=self.headers,
                                  params={'province': '浙江', 'year': 2026, 'page_size': 5})
        self.assertEqual(catalog.status_code, 200, catalog.text)
        item = catalog.json()['items'][0]
        self.assertNotIn('plan_trend', item)  # 列表接口不返回，控制载荷

        detail = self.client.get(f"/api/catalog/{item['id']}", headers=self.headers,
                                 params={'province': '浙江', 'year': 2026})
        self.assertEqual(detail.status_code, 200, detail.text)
        data = detail.json()
        trend = data['plan_trend']
        self.assertEqual([row['year'] for row in trend], [2023, 2024, 2025, 2026])
        self.assertTrue(all(row['seats'] > 0 for row in trend))
        self.assertIsNone(trend[0]['change'])
        for row in trend[1:]:
            self.assertIsInstance(row['change'], float)
        self.assertEqual(data['plan_trend_label'], '模拟样本 · 计划数仅用于演示')


if __name__ == '__main__':
    unittest.main()
