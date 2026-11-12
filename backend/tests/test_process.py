"""录取进程 / 模拟投档结果 / 结果导出 / 征集志愿时间窗测试（临时 SQLite，不连开发库）。

先 import test_workflow 以设置临时 DATABASE_URL；RealAdmission 行与方案都在临时库内构造。
"""
import csv
import io
import json
import os
import secrets
import unittest
from datetime import date
from pathlib import Path

try:
    import test_workflow  # noqa: F401  先设置临时 DATABASE_URL，避免污染开发库
except ImportError:
    from tests import test_workflow  # noqa: F401

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, engine
from app.main import app
from app.models.entities import AuditLog, Plan, RealAdmission
from app.seed import seed
from app.services import process as process_service

PROFILE = {'province': '浙江', 'exam_year': 2026, 'score': 628, 'rank': 22580,
           'subjects': ['物理', '化学', '生物'], 'regions': ['浙江', '江苏', '上海'],
           'majors': ['计算机', '电子信息']}
ASSERT_DATE = date(2026, 11, 11)
PASS_LABEL = '达到近一次官方投档最低位次'
FAIL_LABEL = '未达到近一次官方投档最低位次'
NO_DATA_LABEL = '暂无官方投档数据'


class ProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = os.environ.get('DATABASE_URL', '')
        if url.startswith('sqlite:///'):
            Path(url[len('sqlite:///'):]).parent.mkdir(parents=True, exist_ok=True)
        seed()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()

    # ------------------------------------------------------------- 辅助
    def register(self):
        email = f'{secrets.token_hex(6)}@process-test.cn'
        response = self.client.post('/api/auth/register',
                                    json={'email': email, 'password': 'TestPassword123!', 'name': '进程测试'})
        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        return {'email': email, 'id': payload['user']['id'],
                'headers': {'Authorization': f"Bearer {payload['access_token']}"}}

    def setUp(self):
        self.account = self.register()
        self.user_id = self.account['id']
        self.headers = self.account['headers']

    def save_profile(self, **changes):
        response = self.client.put('/api/auth/profile', headers=self.headers, json={**PROFILE, **changes})
        self.assertEqual(response.status_code, 200, response.text)

    def make_plan(self, university_names, risks=None, name='模拟投档方案', rank=22580):
        risks = risks or ['reach'] * len(university_names)
        with SessionLocal() as db:
            plan = Plan(
                user_id=self.user_id, name=name,
                profile_snapshot={**PROFILE, 'rank': rank},
                items=[{'id': index + 1, 'name': f'专业组{index + 1}',
                        'university': {'name': school}, 'risk': risk}
                       for index, (school, risk) in enumerate(zip(university_names, risks))],
                batch='本科批', status='draft',
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
            return plan.id

    def add_official(self, school, min_rank, year=2025, province='浙江'):
        with SessionLocal() as db:
            db.add(RealAdmission(
                school_name=school, province=province, exam_year=year, subject_type='综合改革',
                batch='普通类', round_no='首次投档', min_score=650, min_rank=min_rank,
                source_url=f'https://example.gov.cn/{year}/tdqk', published_at=f'{year}-07-20',
                fetched_at='2026-11-10T10:00:00+08:00', content_sha256='0' * 64,
                parser_version='test@1.0.0', doc_status='已导入',
            ))
            db.commit()

    # ---------------------------------------------------------- 时间轴
    def test_schedule_auth_structure_and_fallback(self):
        self.assertEqual(self.client.get('/api/process/schedule').status_code, 401)
        self.save_profile()
        response = self.client.get('/api/process/schedule', params={'province': '浙江'}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['province'], '浙江')
        self.assertFalse(data['fallback'])
        self.assertTrue(data['note'])
        self.assertEqual(data['updated_at'], '2026-11')
        self.assertTrue(data['batches'])
        batch = data['batches'][0]
        self.assertEqual({'batch', 'events', 'current_stage', 'next_window'} - set(batch), set())
        self.assertTrue(batch['events'])
        for event in batch['events']:
            self.assertEqual(set(event), {'stage', 'start', 'end', 'status', 'state'})
            self.assertIn(event['state'], {'done', 'active', 'upcoming'})
        self.assertIn(batch['current_stage'], [event['stage'] for event in batch['events']])

        # 不传 province 时使用画像省份
        default = self.client.get('/api/process/schedule', headers=self.headers).json()
        self.assertEqual(default['province'], '浙江')

        # 未收录省份：回退 default 并在 note 标注
        fallback = self.client.get('/api/process/schedule', params={'province': '西藏'},
                                   headers=self.headers).json()
        self.assertTrue(fallback['fallback'])
        self.assertTrue(fallback['batches'])
        self.assertIn('未收录', fallback['note'])

    def test_schedule_state_at_fixed_dates(self):
        done = process_service.schedule('浙江', today=ASSERT_DATE)
        events = done['batches'][0]['events']
        self.assertTrue(all(event['state'] == 'done' for event in events))
        self.assertEqual(done['batches'][0]['current_stage'], '录取结束')
        self.assertIsNone(done['batches'][0]['next_window'])

        active = process_service.schedule('浙江', today=date(2026, 7, 22))
        events = active['batches'][0]['events']
        collect = next(event for event in events if event['stage'] == '征集志愿')
        self.assertEqual(collect['state'], 'active')
        self.assertEqual(active['batches'][0]['current_stage'], '征集志愿')
        self.assertEqual(active['batches'][0]['next_window']['stage'], '录取结束')

        upcoming = process_service.schedule('浙江', today=date(2026, 6, 1))
        events = upcoming['batches'][0]['events']
        self.assertTrue(all(event['state'] == 'upcoming' for event in events))
        self.assertEqual(upcoming['batches'][0]['current_stage'], events[0]['stage'])
        self.assertEqual(upcoming['batches'][0]['next_window']['stage'], events[0]['stage'])

    # ---------------------------------------------------------- 征集窗口
    def test_collection_window_and_days_left(self):
        self.assertEqual(self.client.get('/api/process/collection').status_code, 401)
        self.save_profile()
        response = self.client.get('/api/process/collection', params={'province': '浙江'},
                                   headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual({'batch', 'start', 'end', 'days_left', 'status', 'note'} - set(data), set())
        self.assertEqual(data['batch'], '普通类第一段')
        self.assertIn(data['status'], {'done', 'active', 'upcoming'})
        self.assertIsInstance(data['days_left'], int)

        active = process_service.collection('浙江', today=date(2026, 7, 22))
        self.assertEqual(active['status'], 'active')
        self.assertEqual(active['days_left'], 1)
        self.assertIn('进行中', active['note'])

        upcoming = process_service.collection('浙江', today=date(2026, 7, 1))
        self.assertEqual(upcoming['status'], 'upcoming')
        self.assertEqual(upcoming['days_left'], 21)
        self.assertIn('开始', upcoming['note'])

        done = process_service.collection('浙江', today=ASSERT_DATE)
        self.assertEqual(done['status'], 'done')
        self.assertEqual(done['days_left'], 0)
        self.assertIn('结束', done['note'])

        fallback = process_service.collection('西藏', today=ASSERT_DATE)
        self.assertTrue(fallback['fallback'])
        self.assertEqual(fallback['batch'], '本科批')
        self.assertEqual(fallback['status'], 'done')

    # ------------------------------------------------------ 模拟投档结果
    def test_results_verdicts_labels_and_audit(self):
        self.save_profile()
        plan_id = self.make_plan(['官方甲大学', '官方乙大学', '官方丙大学'],
                                 risks=['reach', 'steady', 'safe'])
        self.add_official('官方甲大学', 22580)  # 位次相等 → 达到
        self.add_official('官方乙大学', 1000)   # 官方最低位次更靠前 → 未达到
        # 官方丙大学不造数据 → no_data

        response = self.client.get(f'/api/process/results/{plan_id}', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['plan_id'], plan_id)
        self.assertEqual(data['plan_name'], '模拟投档方案')
        self.assertEqual(data['province'], '浙江')
        self.assertEqual(data['profile_rank'], 22580)
        self.assertEqual(data['summary'], {'total': 3, 'pass': 1, 'fail': 1, 'no_data': 1})

        items = data['items']
        self.assertEqual(len(items), 3)
        self.assertEqual([item['position'] for item in items], [1, 2, 3])
        for item in items:
            self.assertTrue({'position', 'university', 'group_name', 'risk', 'user_rank',
                             'official', 'verdict', 'label'} <= set(item))
            self.assertEqual(item['user_rank'], 22580)
        self.assertEqual((items[0]['verdict'], items[0]['label']), ('pass', PASS_LABEL))
        self.assertEqual(items[0]['official']['min_rank'], 22580)
        self.assertEqual(items[0]['official']['exam_year'], 2025)
        self.assertEqual((items[1]['verdict'], items[1]['label']), ('fail', FAIL_LABEL))
        self.assertEqual((items[2]['verdict'], items[2]['label']), ('no_data', NO_DATA_LABEL))
        self.assertIsNone(items[2]['official'])
        self.assertEqual(items[0]['risk'], 'reach')

        # 红线：结果条目不得出现概率/百分比；免责声明必须写明"不代表"
        self.assertNotIn('%', json.dumps(data, ensure_ascii=False))
        labels = json.dumps([item['label'] for item in items], ensure_ascii=False)
        self.assertNotIn('概率', labels)
        self.assertNotIn('录取率', json.dumps(data, ensure_ascii=False))
        self.assertIn('不代表', data['disclaimer'])
        self.assertIn('概率', data['disclaimer'])

        with SessionLocal() as db:
            rows = db.scalars(select(AuditLog).where(AuditLog.action == 'result.query')
                              .order_by(AuditLog.id.desc())).all()
        self.assertTrue(rows)
        self.assertEqual(rows[0].target, f'plan:{plan_id}')
        self.assertEqual(rows[0].user_id, self.user_id)

    def test_result_query_pushes_message_once_and_audits(self):
        self.save_profile()
        plan_id = self.make_plan(['官方甲大学'])
        self.add_official('官方甲大学', 22580)
        for _ in range(2):
            response = self.client.get(f'/api/process/results/{plan_id}', headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
        messages = self.client.get('/api/messages', headers=self.headers)
        self.assertEqual(messages.status_code, 200, messages.text)
        pushed = [item for item in messages.json()['items'] if item['type'] == 'result']
        self.assertEqual(len(pushed), 1)
        self.assertIn('模拟投档结果', pushed[0]['title'])
        self.assertIn('不代表录取结果', pushed[0]['body'])
        self.assertEqual(pushed[0]['link'], '/process')
        with SessionLocal() as db:
            rows = db.scalars(select(AuditLog).where(AuditLog.action == 'result.push')).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].target, f'plan:{plan_id}')

    def test_results_owner_scoped_and_auth(self):
        plan_id = self.make_plan(['越权测试大学'])
        self.assertEqual(self.client.get(f'/api/process/results/{plan_id}').status_code, 401)
        self.assertEqual(self.client.get(f'/api/process/results/{plan_id}/export').status_code, 401)

        other = self.register()
        self.assertEqual(self.client.get(f'/api/process/results/{plan_id}',
                                         headers=other['headers']).status_code, 404)
        self.assertEqual(self.client.get(f'/api/process/results/{plan_id}/export',
                                         headers=other['headers']).status_code, 404)

        self.save_profile()
        self.assertEqual(self.client.get(f'/api/process/results/{plan_id}',
                                         headers=self.headers).status_code, 200)

    def test_results_province_without_official_data(self):
        self.save_profile(province='江苏')
        plan_id = self.make_plan(['跨省大学'])
        self.add_official('跨省大学', 30000, province='浙江')  # 官方数据只在浙江
        data = self.client.get(f'/api/process/results/{plan_id}', headers=self.headers).json()
        self.assertEqual(data['province'], '江苏')
        self.assertEqual(data['summary'], {'total': 1, 'pass': 0, 'fail': 0, 'no_data': 1})
        self.assertIsNone(data['items'][0]['official'])
        self.assertEqual(data['items'][0]['verdict'], 'no_data')

    # ------------------------------------------------------------ 导出
    def test_export_csv_bom_header_safe_cell_and_audit(self):
        self.save_profile()
        malicious = '=HYPERLINK("http://evil.example")'
        plan_id = self.make_plan([malicious], risks=['safe'])
        self.add_official(malicious, 30000)

        response = self.client.get(f'/api/process/results/{plan_id}/export', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.content.startswith(b'\xef\xbb\xbf'))
        self.assertIn('text/csv', response.headers['content-type'])
        self.assertIn(f'sunpath-result-{plan_id}.csv', response.headers['content-disposition'])
        text = response.content.decode('utf-8-sig')
        rows = list(csv.reader(io.StringIO(text)))
        self.assertEqual(rows[0], ['序号', '院校', '专业组', '梯度', '你的位次', '官方投档最低位次',
                                   '年份', '科类', '来源链接', '判定'])
        self.assertEqual(rows[1][1], "'" + malicious)  # safe_cell 前缀单引号
        self.assertEqual(rows[1][0], '1')
        self.assertEqual(rows[1][3], '保')
        self.assertEqual(rows[1][4], '22580')
        self.assertEqual(rows[1][5], '30000')
        self.assertEqual(rows[1][6], '2025')
        self.assertEqual(rows[1][9], PASS_LABEL)
        self.assertNotIn('%', text)

        with SessionLocal() as db:
            rows = db.scalars(select(AuditLog).where(AuditLog.action == 'result.export')
                              .order_by(AuditLog.id.desc())).all()
        self.assertTrue(rows)
        self.assertEqual(rows[0].target, f'plan:{plan_id}')
        self.assertEqual(rows[0].user_id, self.user_id)


if __name__ == '__main__':
    unittest.main()
