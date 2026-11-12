"""志愿表 CSV 导入（FR-M6-04）测试：模板、逐行校验、部分成功、审计。

沿用 test_workflow 的临时库模式，先 import 以设置临时 DATABASE_URL。
"""
import csv
import io
import secrets
import unittest

try:
    import test_workflow  # noqa: F401  先设置临时 DATABASE_URL，避免污染开发库
except ImportError:
    from tests import test_workflow  # noqa: F401

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, engine
from app.main import app
from app.models.entities import AuditLog, Plan
from app.seed import seed

PROFILE = {'province': '浙江', 'exam_year': 2026, 'score': 628, 'rank': 22580,
           'subjects': ['物理', '化学', '生物'], 'regions': ['浙江', '江苏', '上海'],
           'majors': ['计算机', '电子信息']}
HEADER = ['序号', '院校名称', '专业组名称', '梯度', '备注']


class PlanImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()

    def register(self):
        email = f'{secrets.token_hex(6)}@import-test.cn'
        response = self.client.post('/api/auth/register',
                                    json={'email': email, 'password': 'TestPassword123!', 'name': '导入测试'})
        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        return {'id': payload['user']['id'],
                'headers': {'Authorization': f"Bearer {payload['access_token']}"}}

    def setUp(self):
        self.account = self.register()
        self.headers = self.account['headers']
        self.client.put('/api/auth/profile', headers=self.headers, json=PROFILE)

    def candidates(self, count=2):
        response = self.client.get('/api/recommendations', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['items'][:count]

    def csv_text(self, rows):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(HEADER)
        for row in rows:
            writer.writerow(row)
        return buffer.getvalue()

    def import_plan(self, content, **extra):
        return self.client.post('/api/plans/import', headers=self.headers,
                                json={'content': content, **extra})

    def test_auth_and_template(self):
        self.assertEqual(self.client.post('/api/plans/import', json={'content': 'x'}).status_code, 401)
        self.assertEqual(self.client.get('/api/plans/import/template').status_code, 401)
        template = self.client.get('/api/plans/import/template', headers=self.headers)
        self.assertEqual(template.status_code, 200, template.text)
        self.assertTrue(template.content.startswith(b'\xef\xbb\xbf'))
        text = template.content.decode('utf-8-sig')
        rows = list(csv.reader(io.StringIO(text)))
        self.assertEqual(rows[0], HEADER)
        self.assertEqual(len(rows), 3)  # 表头 + 2 行示例

    def test_import_creates_draft_and_audit(self):
        items = self.candidates(2)
        rows = [[1, items[0]['university']['name'], items[0]['name'], '冲', ''],
                [2, items[1]['university']['name'], items[1]['name'], '保', '']]
        response = self.import_plan(self.csv_text(rows), name='导入测试方案', batch='本科批')
        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload['report']['total'], 2)
        self.assertEqual(payload['report']['imported'], 2)
        self.assertEqual(payload['report']['rejected'], 0)
        plan = payload['plan']
        self.assertEqual(plan['name'], '导入测试方案')
        self.assertEqual(plan['batch'], '本科批')
        self.assertEqual(plan['status'], 'draft')
        self.assertEqual(len(plan['items']), 2)
        risks = {item['university']['name']: item['risk'] for item in plan['items']}
        self.assertEqual(risks[items[0]['university']['name']], 'reach')
        self.assertEqual(risks[items[1]['university']['name']], 'safe')

        with SessionLocal() as db:
            saved = db.get(Plan, plan['id'])
            self.assertIsNotNone(saved)
            logs = db.scalars(select(AuditLog).where(AuditLog.action == 'plan.import')).all()
            self.assertTrue(logs)
            self.assertEqual(logs[-1].target, f"plan:{plan['id']}")
            self.assertEqual(logs[-1].detail['imported'], 2)

    def test_partial_import_reports_reasons(self):
        items = self.candidates(1)
        rows = [[1, items[0]['university']['name'], items[0]['name'], '稳', ''],
                [2, '不存在的大学', '', '冲', ''],
                [3, items[0]['university']['name'], items[0]['name'], '稳', '重复行']]
        response = self.import_plan(self.csv_text(rows))
        self.assertEqual(response.status_code, 201, response.text)
        report = response.json()['report']
        self.assertEqual(report['imported'], 1)
        self.assertEqual(report['rejected'], 2)
        reasons = ' '.join(item['reason'] for item in report['errors'])
        self.assertIn('未收录该院校', reasons)
        self.assertIn('重复', reasons)
        self.assertEqual([item['line'] for item in report['errors']], [3, 4])

    def test_rejects_when_nothing_valid(self):
        content = self.csv_text([[1, '不存在的大学', '', '', '']])
        response = self.import_plan(content)
        self.assertEqual(response.status_code, 400, response.text)
        detail = response.json()
        self.assertIn('没有可导入的行', detail['detail'])
        self.assertEqual(detail['report']['imported'], 0)

    def test_rejects_bad_header_and_empty(self):
        response = self.import_plan('学校,专业\n浙江大学,工科\n')
        self.assertEqual(response.status_code, 400)
        self.assertIn('缺少表头', response.json()['detail'])
        empty = self.import_plan(self.csv_text([]))
        self.assertEqual(empty.status_code, 400)
        self.assertIn('没有数据行', empty.json()['detail'])

    def test_requires_profile(self):
        fresh = self.register()
        content = self.csv_text([[1, '浙江大学', '', '', '']])
        response = self.client.post('/api/plans/import', headers=fresh['headers'],
                                    json={'content': content})
        self.assertIn(response.status_code, (400, 422), response.text)


if __name__ == '__main__':
    unittest.main()
