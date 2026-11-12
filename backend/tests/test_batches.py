"""M10-01 批次与填报时间配置的隔离测试（临时 SQLite，不连开发库）。

复用 test_workflow 的临时库模式（先 ``import test_workflow`` 让它在导入 app 前设置 DATABASE_URL）；
管理员身份用 patch ``app.core.security.get_settings`` 注入 admin_emails，不依赖本机 .env。
"""
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import test_workflow  # noqa: F401  先设置临时 DATABASE_URL，避免污染开发库
except ImportError:
    from tests import test_workflow  # noqa: F401

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.main import app
from app.models.entities import BatchConfig
from app.seed import seed
from app.services.batches import ensure_defaults

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_NAMES = ['本科批', '专科批']
NOTE_TEXT = '批次与填报时间以省考试院公告为准'


class BatchesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()
        with SessionLocal() as db:
            ensure_defaults(db)
            db.commit()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()

    def setUp(self):
        self.reset_batches()
        self.user, self.headers = self.account('批次测试')
        self.admin_email = f'admin-{secrets.token_hex(4)}@test.cn'
        self.admin, self.admin_headers = self.account('管理员', email=self.admin_email)

    # ---------------------------------------------------------------- helpers
    def account(self, name, email=None):
        email = email or f'{secrets.token_hex(8)}@test.cn'
        response = self.client.post('/api/auth/register',
                                    json={'email': email, 'password': 'TestPassword123!', 'name': name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['user'], {'Authorization': f"Bearer {response.json()['access_token']}"}

    def reset_batches(self):
        """每个用例前把两行重置为默认值，避免用例间顺序耦合。"""
        with SessionLocal() as db:
            rows = {row.name: row for row in db.scalars(select(BatchConfig)).all()}
            for name, sort_order in (('本科批', 1), ('专科批', 2)):
                row = rows.get(name)
                if row is None:
                    db.add(BatchConfig(name=name, active=True, sort_order=sort_order))
                else:
                    row.active = True
                    row.sort_order = sort_order
                    row.fill_start = None
                    row.fill_end = None
                    row.note = None
            db.commit()

    def admin_patch(self, emails=None):
        emails = [self.admin_email] if emails is None else emails
        return patch('app.core.security.get_settings',
                     return_value=get_settings().model_copy(update={'admin_emails': emails}))

    def put_batches(self, body, headers=None):
        with self.admin_patch():
            return self.client.put('/api/ops/batches', headers=headers or self.admin_headers, json=body)

    def config(self, headers=None, **params):
        response = self.client.get('/api/batches', headers=headers or self.headers, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    # ---------------------------------------------------------------- 读取
    def test_default_batches_sorted_and_readable(self):
        self.assertEqual(self.client.get('/api/batches').status_code, 401)
        payload = self.config()
        self.assertEqual(payload['note'], NOTE_TEXT)
        items = payload['items']
        self.assertEqual([item['name'] for item in items], DEFAULT_NAMES)
        self.assertEqual([item['sort_order'] for item in items], [1, 2])
        self.assertTrue(all(item['active'] for item in items))
        self.assertEqual(set(items[0]),
                         {'name', 'active', 'sort_order', 'fill_start', 'fill_end', 'note', 'updated_at'})
        self.assertIsNotNone(items[0]['updated_at'])
        self.assertIsNone(items[0]['fill_start'])
        self.assertIsNone(items[0]['fill_end'])

    # ---------------------------------------------------------------- 权限
    def test_update_requires_admin(self):
        body = {'batches': [{'name': '本科批', 'active': True, 'sort_order': 1}]}
        self.assertEqual(self.client.put('/api/ops/batches', json=body).status_code, 401)
        with self.admin_patch(emails=[]):
            response = self.client.put('/api/ops/batches', headers=self.headers, json=body)
        self.assertEqual(response.status_code, 403, response.text)
        self.assertIn('管理员', response.json()['detail'])
        # 普通用户（即使 .env 里配了 demo 管理员）在 patch 白名单为空时一律 403，且配置未被改动
        self.assertEqual([item['name'] for item in self.config()['items']], DEFAULT_NAMES)

    # ---------------------------------------------------------------- 更新 + 持久化 + 审计
    def test_admin_update_persists_and_audits(self):
        body = {'batches': [
            {'name': '本科批', 'active': True, 'sort_order': 1,
             'fill_start': '2026-06-25', 'fill_end': '2026-06-30', 'note': '示例：本科批填报时间'},
            {'name': '专科批', 'active': False, 'sort_order': 5,
             'fill_start': None, 'fill_end': None, 'note': '暂停展示'},
        ]}
        response = self.put_batches(body)
        self.assertEqual(response.status_code, 200, response.text)
        items = response.json()['items']
        self.assertEqual([item['name'] for item in items], ['本科批', '专科批'])
        self.assertEqual(items[0]['fill_start'], '2026-06-25')
        self.assertEqual(items[0]['fill_end'], '2026-06-30')
        self.assertEqual(items[0]['note'], '示例：本科批填报时间')
        self.assertFalse(items[1]['active'])
        self.assertEqual(items[1]['sort_order'], 5)
        self.assertIsNone(items[1]['fill_start'])

        # 持久化：换会话重新读取一致
        self.assertEqual(self.config()['items'], items)
        paused = self.config(active_only=True)['items']
        self.assertEqual([item['name'] for item in paused], ['本科批'])

        # 审计：detail.changed 记录实际变更的批次名（首次两条都变）
        updates = [item for item in self.client.get('/api/ops/audit', headers=self.admin_headers).json()['items']
                   if item['action'] == 'batch.update']
        self.assertEqual(len(updates), 1)
        self.assertEqual(sorted(updates[0]['detail']['changed']), ['专科批', '本科批'])

        # 同样内容再 PUT：成功但 detail.changed 为空（幂等，不虚报变更）
        self.assertEqual(self.put_batches(body).status_code, 200)
        updates = [item for item in self.client.get('/api/ops/audit', headers=self.admin_headers).json()['items']
                   if item['action'] == 'batch.update']
        self.assertEqual(len(updates), 2)
        self.assertEqual(updates[0]['detail']['changed'], [])

    # ---------------------------------------------------------------- 校验
    def test_update_validation_errors(self):
        base = {'name': '本科批', 'active': True, 'sort_order': 1}
        self.assertEqual(self.put_batches({'batches': [{**base, 'name': '提前批'}]}).status_code, 400)
        for bad_date in ('2026-13-01', '2026/06/01', '20260601', 'x'):
            response = self.put_batches({'batches': [{**base, 'fill_start': bad_date}]})
            self.assertEqual(response.status_code, 400, (bad_date, response.text))
        reversed_range = self.put_batches({'batches': [{**base, 'fill_start': '2026-07-01',
                                                        'fill_end': '2026-06-30'}]})
        self.assertEqual(reversed_range.status_code, 400, reversed_range.text)
        self.assertEqual(self.put_batches({'batches': [{**base, 'active': 'maybe'}]}).status_code, 422)
        self.assertEqual(self.put_batches({'batches': [{**base, 'sort_order': 'abc'}]}).status_code, 422)
        self.assertEqual(self.put_batches({'batches': []}).status_code, 422)
        self.assertEqual(self.put_batches({'batches': [{**base}, {**base}]}).status_code, 400)

        # 备注截断 200
        saved = self.put_batches({'batches': [{**base, 'note': 'x' * 250}]})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(len(saved.json()['items'][0]['note']), 200)

        # 校验失败不部分写入，也不会新增/删除批次
        items = self.config()['items']
        self.assertEqual([item['name'] for item in items], DEFAULT_NAMES)
        self.assertEqual(items[0]['note'], 'x' * 200)
        self.assertIsNone(items[0]['fill_start'])

    # ---------------------------------------------------------------- 迁移幂等
    def test_migrate_v5_is_idempotent(self):
        script = BACKEND_DIR / 'scripts' / 'migrate_v5.py'
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / 'migrate_v5.db'
            db_path.touch()
            environment = {
                **os.environ,
                'DATABASE_URL': 'sqlite:///' + db_path.as_posix(),
                'JWT_SECRET': secrets.token_urlsafe(48),
                'PYTHONIOENCODING': 'utf-8',
            }
            outputs = []
            for _ in range(2):
                result = subprocess.run([sys.executable, str(script), '--no-backup'],
                                        cwd=str(BACKEND_DIR), env=environment,
                                        capture_output=True, text=True, encoding='utf-8', timeout=120)
                self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
                outputs.append(result.stdout)
            self.assertIn('新增默认批次 2 个', outputs[0])
            self.assertIn('新增默认批次 0 个', outputs[1])

            connection = sqlite3.connect(db_path)
            try:
                rows = connection.execute(
                    'SELECT name, sort_order, active FROM batch_configs ORDER BY sort_order, name').fetchall()
            finally:
                connection.close()
            self.assertEqual(rows, [('本科批', 1, 1), ('专科批', 2, 1)])


if __name__ == '__main__':
    unittest.main()
