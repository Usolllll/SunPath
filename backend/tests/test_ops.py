"""运营治理接口测试：FAQ / 数据字典 / 质量看板 / 审计 / 热度 / 备份恢复 / 画像完整度。

复用 test_workflow 的临时 SQLite 模式（先 import 设置 DATABASE_URL），不连开发库。
"""
import csv
import hashlib
import io
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import unquote

try:
    import test_workflow  # noqa: F401  先设置临时 DATABASE_URL，避免污染开发库
except ImportError:
    from tests import test_workflow  # noqa: F401

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.main import app
from app.models.entities import AuditLog, DataVersion, Favorite, Message, Plan, Profile, University
from app.schemas.dto import PROVINCES
from app.seed import seed

BACKEND_DIR = Path(__file__).resolve().parents[1]
PASSWORD = 'OpsTestPassword123!'
NEW_PASSWORD = 'OpsTestPassword456!'
PROFILE = {
    'province': '浙江', 'exam_year': 2026, 'score': 628, 'rank': 22580,
    'subjects': ['物理', '化学', '生物'], 'regions': ['浙江', '江苏', '上海'],
    'majors': ['计算机', '电子信息'], 'priority_mode': 'balanced',
    'interests': {'R': 40, 'I': 80, 'A': 30, 'S': 50, 'E': 40, 'C': 60},
    'budget_total': 150000, 'physical': {'color_weak': False},
}
COMPLETENESS_FIELDS = ['province', 'exam_year', 'score', 'rank', 'subjects', 'regions',
                       'majors', 'priority_mode', 'interests', 'budget_total', 'physical']
FAQ_ITEM_FIELDS = {'id', 'category', 'question', 'answer', 'source', 'source_url'}
AUDIT_ITEM_FIELDS = {'id', 'action', 'target', 'detail', 'ip', 'created_at'}


class OpsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 兼容其他测试类先跑完并清理临时目录的情况：确保临时库目录存在再建表
        url = os.environ.get('DATABASE_URL', '')
        if url.startswith('sqlite:///'):
            Path(url[len('sqlite:///'):]).parent.mkdir(parents=True, exist_ok=True)
        seed()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()

    def register(self, name='运营测试'):
        email = f'{secrets.token_hex(6)}@ops-test.cn'
        response = self.client.post('/api/auth/register',
                                    json={'email': email, 'password': PASSWORD, 'name': name})
        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        return {'email': email, 'id': payload['user']['id'], 'token': payload['access_token'],
                'headers': {'Authorization': f"Bearer {payload['access_token']}"}}

    def login(self, email, password):
        return self.client.post('/api/auth/login', json={'email': email, 'password': password})

    # ------------------------------------------------------------------ FAQ
    def test_faq_search_filters_and_empty(self):
        # FAQ 为公开只读接口，无令牌也可访问
        response = self.client.get('/api/ops/faq', params={'q': '体检'})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(set(data), {'total', 'categories', 'items'})
        self.assertEqual(data['total'], len(data['items']))
        self.assertIn('FAQ-03', [item['id'] for item in data['items']])
        faq03 = next(item for item in data['items'] if item['id'] == 'FAQ-03')
        self.assertEqual(set(faq03), FAQ_ITEM_FIELDS)
        self.assertIn('体检', faq03['answer'])
        self.assertEqual(data['categories'],
                         ['报名与资格', '志愿与梯度', '数据与来源', '预算与成本', '系统使用'])

        filtered = self.client.get('/api/ops/faq', params={'category': '数据与来源'}).json()
        self.assertEqual(filtered['total'], 3)
        self.assertTrue(all(item['category'] == '数据与来源' for item in filtered['items']))

        keyword = self.client.get('/api/ops/faq', params={'q': '平行志愿'}).json()
        self.assertIn('FAQ-04', [item['id'] for item in keyword['items']])

        empty = self.client.get('/api/ops/faq', params={'q': '不存在的关键词xyz'}).json()
        self.assertEqual((empty['total'], empty['items']), (0, []))

    # ------------------------------------------------------------- 数据字典
    def test_dictionary_contract(self):
        response = self.client.get('/api/ops/dictionary')
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        for key in ('provinces', 'subjects', 'levels', 'city_tiers', 'batches', 'modes',
                    'risks', 'budget_tiers', 'data_sources'):
            self.assertIn(key, data)
        self.assertEqual(data['provinces'], PROVINCES)
        self.assertEqual(data['batches'], ['本科批', '专科批'])
        self.assertEqual(data['levels'],
                         ['985 / 211 / 双一流', '211 / 双一流', '双一流', '省重点', '其他'])

        self.assertEqual([tier['tier'] for tier in data['city_tiers']], [1, 2, 3, 4])
        for tier in data['city_tiers']:
            self.assertTrue(tier['cities'])
        self.assertIn('北京', data['city_tiers'][0]['cities'])

        modes = {mode['key']: mode for mode in data['modes']}
        self.assertEqual(set(modes), {'school', 'balanced', 'major'})
        for mode in modes.values():
            self.assertEqual(set(mode['weights']), {'school', 'major', 'fit'})
            self.assertAlmostEqual(sum(mode['weights'].values()), 1.0, places=6)

        self.assertEqual(set(data['risks']), {'reach', 'steady', 'safe'})
        self.assertTrue(data['budget_tiers'])
        self.assertTrue(all({'name', 'range'} <= set(tier) for tier in data['budget_tiers']))

        sources = {source['id']: source for source in data['data_sources']}
        self.assertIn('MOE-LIST', sources)
        for source in sources.values():
            self.assertEqual(set(source), {'id', 'dataset', 'province', 'automation'})

    # ------------------------------------------------------------- 质量看板
    def test_data_quality_dashboard_structure(self):
        response = self.client.get('/api/ops/data-quality')
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        for key in ('generated_at', 'simulated', 'real', 'versions', 'patrol', 'counts', 'disclaimer'):
            self.assertIn(key, data)
        datetime.fromisoformat(data['generated_at'])

        simulated = data['simulated']
        self.assertEqual(simulated['universities'], 60)
        self.assertEqual(simulated['groups'], 120)
        self.assertEqual(simulated['admissions'], 60 * 2 * len(PROVINCES) * 3)
        self.assertEqual(simulated['enrollments'], 60 * 2 * len(PROVINCES) * 4)
        self.assertGreater(simulated['major_cards'], 0)

        real = data['real']
        self.assertEqual(real['total_rows'], sum(item['rows'] for item in real['provinces']))
        self.assertIsInstance(real['provinces'], list)
        self.assertIsInstance(data['versions'], list)

        self.assertEqual(data['counts']['faq'], 15)
        self.assertGreaterEqual(data['counts']['audit_logs'], 0)
        for key in ('favorites', 'audit_logs', 'plans'):
            self.assertIsInstance(data['counts'][key], int)

        patrol = data['patrol']
        if patrol is not None:
            self.assertIn('last_checked_at', patrol)
            for item in patrol['items']:
                self.assertTrue({'id', 'dataset', 'ok', 'status', 'changed', 'checked_at'} <= set(item))
        self.assertTrue(data['disclaimer'])

    # ------------------------------------------------------------------ 审计
    def test_audit_is_owner_scoped_and_paginated(self):
        first = self.register('审计甲')
        second = self.register('审计乙')
        for account in (first, second):
            self.assertEqual(self.login(account['email'], PASSWORD).status_code, 200)

        own = self.client.get('/api/ops/audit', headers=first['headers'])
        self.assertEqual(own.status_code, 200, own.text)
        data = own.json()
        self.assertGreaterEqual(data['total'], 2)
        self.assertEqual(data['total'], len(data['items']))
        for item in data['items']:
            self.assertEqual(set(item), AUDIT_ITEM_FIELDS)
        actions = {item['action'] for item in data['items']}
        self.assertTrue({'auth.register', 'auth.login'} <= actions)

        other = self.client.get('/api/ops/audit', headers=second['headers']).json()
        self.assertTrue({item['id'] for item in data['items']}
                        .isdisjoint({item['id'] for item in other['items']}))
        with SessionLocal() as db:
            rows = db.scalars(select(AuditLog).where(
                AuditLog.id.in_([item['id'] for item in data['items']]))).all()
            self.assertTrue(all(row.user_id == first['id'] for row in rows))

        page = self.client.get('/api/ops/audit', params={'limit': 1}, headers=first['headers']).json()
        self.assertEqual(len(page['items']), 1)
        self.assertEqual(page['total'], data['total'])
        second_page = self.client.get('/api/ops/audit', params={'limit': 1, 'offset': 1},
                                      headers=first['headers']).json()
        self.assertNotEqual(page['items'][0]['id'], second_page['items'][0]['id'])
        created = [item['created_at'] for item in data['items'] if item['created_at']]
        self.assertEqual(created, sorted(created, reverse=True))

        self.assertEqual(self.client.get('/api/ops/audit').status_code, 401)

    # ------------------------------------------------- 审计钩子（auth 全流程）
    def test_auth_audit_hooks_without_secrets(self):
        account = self.register('审计钩子')
        headers = account['headers']
        self.assertEqual(self.login(account['email'], PASSWORD).status_code, 200)
        self.assertEqual(self.client.put('/api/auth/profile', headers=headers, json=PROFILE).status_code, 200)
        self.assertEqual(self.login(account['email'], 'WrongPassword123!').status_code, 401)
        self.assertEqual(self.client.put('/api/auth/password', headers=headers,
                                         json={'current_password': PASSWORD, 'new_password': NEW_PASSWORD}).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me', headers=headers).status_code, 401)
        fresh = self.login(account['email'], NEW_PASSWORD)
        self.assertEqual(fresh.status_code, 200)
        fresh_headers = {'Authorization': f"Bearer {fresh.json()['access_token']}"}
        self.assertEqual(self.client.post('/api/auth/logout', headers=fresh_headers).status_code, 200)
        again = self.login(account['email'], NEW_PASSWORD)
        self.assertEqual(again.status_code, 200)
        again_headers = {'Authorization': f"Bearer {again.json()['access_token']}"}

        data = self.client.get('/api/ops/audit', params={'limit': 50}, headers=again_headers).json()
        actions = {item['action'] for item in data['items']}
        self.assertTrue({'auth.register', 'auth.login', 'profile.save',
                         'auth.password', 'auth.logout'} <= actions)
        serialized = json.dumps(data, ensure_ascii=False)
        for secret in (account['email'], PASSWORD, NEW_PASSWORD, 'Bearer'):
            self.assertNotIn(secret, serialized)
        for item in data['items']:
            self.assertIsNone(item['detail'])

        with SessionLocal() as db:
            failed = db.scalar(select(AuditLog).where(AuditLog.action == 'auth.login_failed')
                               .order_by(AuditLog.id.desc()))
            self.assertIsNotNone(failed)
            self.assertIsNone(failed.user_id)
            self.assertIsNone(failed.target)
            self.assertNotIn(account['email'], json.dumps(failed.detail or {}, ensure_ascii=False))

    # ------------------------------------------------------------------ 热度
    def test_popularity_ranking_and_empty_note(self):
        with SessionLocal() as db:
            db.execute(delete(Favorite))
            db.commit()
        empty = self.client.get('/api/ops/popularity')
        self.assertEqual(empty.json(), [])
        self.assertEqual(unquote(empty.headers.get('x-popularity-note', '')), '暂无用户收藏数据。')

        first = self.register('热度甲')
        second = self.register('热度乙')
        third = self.register('热度丙')
        with SessionLocal() as db:
            universities = db.scalars(select(University).order_by(University.id).limit(3)).all()
            ids = [university.id for university in universities]
            db.add_all([
                Favorite(user_id=first['id'], university_id=ids[0]),
                Favorite(user_id=second['id'], university_id=ids[0]),
                Favorite(user_id=first['id'], university_id=ids[1]),
                Favorite(user_id=third['id'], university_id=ids[2]),
            ])
            db.commit()

        response = self.client.get('/api/ops/popularity', params={'limit': 10})
        items = response.json()
        self.assertIsInstance(items, list)
        self.assertEqual(items[0]['university_id'], ids[0])
        self.assertEqual(items[0]['favorites'], 2)
        self.assertEqual([item['favorites'] for item in items], [2, 1, 1])
        self.assertEqual({item['university_id'] for item in items}, set(ids))
        self.assertEqual(set(items[0]), {'university_id', 'name', 'city', 'region', 'level',
                                         'level_tier', 'favorites'})
        self.assertEqual(self.client.get('/api/ops/popularity',
                                         params={'limit': 1}).json()[0]['university_id'], ids[0])

    # ------------------------------------------------------- 画像完整度
    def test_profile_completeness_scores(self):
        account = self.register('完整度')
        headers = account['headers']
        self.assertEqual(self.client.get('/api/ops/profile-completeness').status_code, 401)
        empty = self.client.get('/api/ops/profile-completeness', headers=headers).json()
        self.assertEqual(empty, {'score': 0, 'filled': [], 'missing': COMPLETENESS_FIELDS})

        saved = self.client.put('/api/auth/profile', headers=headers, json=PROFILE)
        self.assertEqual(saved.status_code, 200, saved.text)
        full = self.client.get('/api/ops/profile-completeness', headers=headers).json()
        self.assertEqual(full['score'], 100)
        self.assertEqual(full['missing'], [])
        self.assertEqual(full['filled'], COMPLETENESS_FIELDS)

        with SessionLocal() as db:
            profile = db.scalar(select(Profile).where(Profile.user_id == account['id']))
            self.assertIsNotNone(profile)
            profile.regions, profile.majors = [], []
            profile.priority_mode = None
            profile.interests = profile.budget_total = profile.physical = None
            db.commit()
        partial = self.client.get('/api/ops/profile-completeness', headers=headers).json()
        self.assertEqual(partial['score'], 55)
        self.assertEqual(partial['filled'], COMPLETENESS_FIELDS[:5])
        self.assertEqual(partial['missing'], COMPLETENESS_FIELDS[5:])

    # ------------------------------------------------------- 备份 / 恢复
    def test_backup_and_restore_roundtrip(self):
        script = BACKEND_DIR / 'scripts' / 'backup_restore.py'
        with tempfile.TemporaryDirectory(prefix='sunpath-ops-backup-') as raw:
            root = Path(raw)
            database = root / 'source.db'
            connection = sqlite3.connect(database)
            connection.executescript("""
                CREATE TABLE data_versions (id INTEGER PRIMARY KEY, dataset TEXT, province TEXT, row_count INTEGER);
                INSERT INTO data_versions (id, dataset, province, row_count) VALUES (1, '投档线', '辽宁', 2);
                CREATE TABLE marker (value TEXT);
                INSERT INTO marker (value) VALUES ('original');
            """)
            connection.commit()
            connection.close()

            env = os.environ.copy()
            env['DATABASE_URL'] = 'sqlite:///' + database.as_posix()
            out = root / 'backups'
            backup_run = subprocess.run(
                [sys.executable, str(script), 'backup', '--out', str(out)],
                cwd=str(BACKEND_DIR), env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(backup_run.returncode, 0, backup_run.stderr)
            result = json.loads(backup_run.stdout.strip().splitlines()[-1])
            backup_file = Path(result['backup_file'])
            manifest_file = Path(result['manifest_file'])
            self.assertTrue(backup_file.exists())
            manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
            self.assertEqual(manifest['sha256'], hashlib.sha256(backup_file.read_bytes()).hexdigest())
            self.assertEqual(manifest['size_bytes'], backup_file.stat().st_size)
            self.assertIn('created_at', manifest)
            versions = json.loads(Path(result['data_versions_file']).read_text(encoding='utf-8'))
            self.assertEqual(len(versions['items']), 1)
            self.assertEqual(versions['items'][0]['dataset'], '投档线')

            connection = sqlite3.connect(database)
            connection.execute("INSERT INTO marker (value) VALUES ('changed')")
            connection.commit()
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM marker').fetchone()[0], 2)
            connection.close()

            refused = subprocess.run(
                [sys.executable, str(script), 'restore', '--file', str(backup_file)],
                cwd=str(BACKEND_DIR), env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(refused.returncode, 2, refused.stdout)
            connection = sqlite3.connect(database)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM marker').fetchone()[0], 2)
            connection.close()

            restored = subprocess.run(
                [sys.executable, str(script), 'restore', '--file', str(backup_file), '--yes',
                 '--out', str(root / 'pre-restore')],
                cwd=str(BACKEND_DIR), env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(restored.returncode, 0, restored.stderr)
            restore_result = json.loads(restored.stdout.strip().splitlines()[-1])
            self.assertTrue(Path(restore_result['pre_backup']).exists())
            connection = sqlite3.connect(database)
            try:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM marker').fetchone()[0], 1)
                self.assertEqual(connection.execute('SELECT value FROM marker').fetchone()[0], 'original')
            finally:
                connection.close()

    # ------------------------------------------------ 管理员看板（M9）
    @contextmanager
    def admin_mode(self, email=None):
        """仅在请求期间把管理员白名单换成指定邮箱，避免受本机 .env 的 ADMIN_EMAILS 影响。"""
        settings = get_settings()
        stub = SimpleNamespace(jwt_secret=settings.jwt_secret,
                               admin_emails=[email.strip().lower()] if email else [])
        with patch('app.core.security.get_settings', return_value=stub):
            yield

    def audit_row(self, action, when, user_id=None):
        with SessionLocal() as db:
            db.add(AuditLog(user_id=user_id, action=action, created_at=when))
            db.commit()

    def plan_row(self, items, batch='本科批', status='draft', user_id=None):
        with SessionLocal() as db:
            plan = Plan(user_id=user_id, name='运营统计方案', items=items,
                        profile_snapshot={**PROFILE}, batch=batch, status=status)
            db.add(plan)
            db.commit()
            db.refresh(plan)
            return plan.id

    def test_admin_endpoints_require_admin(self):
        account = self.register('普通用户')
        paths = ['/api/ops/behavior', '/api/ops/tier-distribution',
                 '/api/ops/report', '/api/ops/report/export']
        with self.admin_mode(None):
            for path in paths:
                response = self.client.get(path, headers=account['headers'])
                self.assertEqual(response.status_code, 403, path)
                self.assertIn('管理员', response.json()['detail'])
                self.assertEqual(self.client.get(path).status_code, 401)

        admin = self.register('管理员')
        with self.admin_mode(admin['email']):
            for path in paths:
                self.assertEqual(self.client.get(path, headers=admin['headers']).status_code, 200, path)
            for days in (6, 91):
                self.assertEqual(self.client.get('/api/ops/behavior', params={'days': days},
                                                 headers=admin['headers']).status_code, 422)
                self.assertEqual(self.client.get('/api/ops/report', params={'days': days},
                                                 headers=admin['headers']).status_code, 422)

    def test_admin_behavior_series_zero_fill_and_totals(self):
        admin = self.register('管理员')
        now = datetime.now(timezone.utc)
        today = now.date()
        # discover 时同一临时库里可能有其他测试类的审计记录，先取基线再做增量断言
        with self.admin_mode(admin['email']):
            baseline = self.client.get('/api/ops/behavior', params={'days': 7},
                                       headers=admin['headers']).json()
        for action, when in [
            ('plan.create', now - timedelta(days=1)),
            ('plan.create', now - timedelta(days=1)),
            ('favorite.add', now - timedelta(days=3)),
            ('result.query', now),
            ('plan.submit', now - timedelta(days=10)),  # 7 天窗口外，不计
            ('auth.login', now),                        # 非统计 action，不计
        ]:
            self.audit_row(action, when, admin['id'])

        with self.admin_mode(admin['email']):
            response = self.client.get('/api/ops/behavior', params={'days': 7},
                                       headers=admin['headers'])
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['days'], 7)
        self.assertEqual(len(data['series']), 7)
        expected_dates = [(today - timedelta(days=6 - index)).isoformat() for index in range(7)]
        self.assertEqual([item['date'] for item in data['series']], expected_dates)
        self.assertEqual(set(data['series'][0]),
                         {'date', 'register', 'plan_create', 'plan_submit',
                          'result_query', 'favorite_add'})
        by_date = {item['date']: item for item in data['series']}
        base_by_date = {item['date']: item for item in baseline['series']}
        yesterday = (today - timedelta(days=1)).isoformat()
        delta = {key: data['totals'][key] - baseline['totals'][key] for key in data['totals']}
        self.assertEqual(delta['plan_create'], 2)
        self.assertEqual(delta['favorite_add'], 1)
        self.assertEqual(delta['result_query'], 1)
        self.assertEqual(delta['plan_submit'], 0)  # 10 天前不在 7 天窗口
        self.assertGreaterEqual(by_date[today.isoformat()]['register'], 1)  # 本次注册写了一条
        date_delta = {key: by_date[yesterday][key] - base_by_date[yesterday][key] for key in delta}
        self.assertEqual(date_delta['plan_create'], 2)
        today_delta = {key: by_date[today.isoformat()][key] - base_by_date[today.isoformat()][key]
                       for key in delta}
        self.assertEqual(today_delta['result_query'], 1)
        window_start = expected_dates[0]
        self.assertEqual(by_date[window_start]['plan_create'],
                         base_by_date[window_start]['plan_create'])  # 补零/无新增
        self.assertEqual(data['totals'],
                         {key: sum(item[key] for item in data['series']) for key in data['totals']})
        self.assertIn('审计日志', data['note'])

    def test_admin_tier_distribution(self):
        account = self.register('管理员')
        self.plan_row([{'risk': 'reach'}, {'risk': 'reach'}, {'risk': 'steady'},
                       {'risk': 'safe'}, {'risk': 'bogus'}, {'no_risk': True}],
                      batch='本科批', user_id=account['id'])
        self.plan_row([{'risk': 'reach'}, {'risk': 'safe'}, {'risk': 'safe'}],
                      batch='专科批', user_id=account['id'])

        with self.admin_mode(account['email']):
            response = self.client.get('/api/ops/tier-distribution', headers=account['headers'])
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()

        with SessionLocal() as db:
            plans = db.scalars(select(Plan)).all()
        expected_tiers = {'reach': 0, 'steady': 0, 'safe': 0}
        expected_batch = {}
        for plan in plans:
            counts = expected_batch.setdefault(plan.batch or '本科批',
                                               {'reach': 0, 'steady': 0, 'safe': 0})
            for item in plan.items or []:
                risk = item.get('risk') if isinstance(item, dict) else None
                if risk in expected_tiers:
                    expected_tiers[risk] += 1
                    counts[risk] += 1
        self.assertEqual(data['total_plans'], len(plans))
        self.assertEqual(data['tiers'], expected_tiers)
        by_batch = {row['batch']: row for row in data['by_batch']}
        self.assertEqual(set(by_batch), set(expected_batch))
        for batch, counts in expected_batch.items():
            self.assertEqual({key: by_batch[batch][key] for key in expected_tiers}, counts)
        self.assertGreaterEqual(by_batch['本科批']['reach'], 2)
        self.assertGreaterEqual(by_batch['专科批']['safe'], 2)
        self.assertEqual(data['note'], '按已保存方案的梯度标记统计')

    def test_admin_report_and_export(self):
        account = self.register('管理员')
        with SessionLocal() as db:
            university_id = db.scalar(select(University.id).order_by(University.id))
            db.add(Favorite(user_id=account['id'], university_id=university_id))
            db.add(Message(user_id=account['id'], type='system', title='运营报表测试',
                           body='正文', dedupe_key=f'test:report:{account["id"]}'))
            db.add(Message(user_id=account['id'], type='system', title='已读消息', body='正文',
                           read_at=datetime.now(timezone.utc)))
            db.commit()
        self.plan_row([{'risk': 'reach'}, {'risk': 'safe'}], status='submitted',
                      user_id=account['id'])

        with self.admin_mode(account['email']):
            response = self.client.get('/api/ops/report', params={'days': 30},
                                       headers=account['headers'])
            exported = self.client.get('/api/ops/report/export', params={'days': 30},
                                       headers=account['headers'])
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        for key in ('generated_at', 'period_days', 'users', 'plans', 'favorites',
                    'messages', 'tiers', 'behavior_totals', 'quality', 'note'):
            self.assertIn(key, data)
        datetime.fromisoformat(data['generated_at'])
        self.assertEqual(data['period_days'], 30)
        self.assertEqual(set(data['users']), {'total', 'new_in_period'})
        self.assertEqual(set(data['plans']), {'total', 'submitted', 'new_in_period'})
        self.assertEqual(set(data['messages']), {'total', 'unread'})
        self.assertEqual(set(data['tiers']), {'reach', 'steady', 'safe'})
        self.assertEqual(set(data['behavior_totals']),
                         {'register', 'plan_create', 'plan_submit', 'result_query', 'favorite_add'})
        self.assertIsInstance(data['quality'], dict)
        self.assertGreaterEqual(data['users']['total'], 1)
        self.assertGreaterEqual(data['users']['new_in_period'], 1)
        self.assertGreaterEqual(data['plans']['total'], 1)
        self.assertGreaterEqual(data['plans']['submitted'], 1)
        self.assertGreaterEqual(data['favorites']['total'], 1)
        self.assertGreaterEqual(data['messages']['total'], 2)
        self.assertGreaterEqual(data['messages']['unread'], 1)
        self.assertTrue(data['note'])

        self.assertEqual(exported.status_code, 200, exported.text)
        self.assertTrue(exported.content.startswith(b'\xef\xbb\xbf'))
        self.assertIn('text/csv', exported.headers['content-type'])
        self.assertRegex(exported.headers['content-disposition'],
                         r'sunpath-report-\d{8}\.csv')
        text = exported.content.decode('utf-8-sig')
        rows = list(csv.reader(io.StringIO(text)))
        flat = '\n'.join('|'.join(row) for row in rows)
        for label in ('用户总数', '方案总数', '收藏总数', '消息总数', '梯度分布', '行为合计'):
            self.assertIn(label, flat)
        self.assertIn(str(data['plans']['total']), flat)

        with SessionLocal() as db:
            audit_rows = db.scalars(select(AuditLog).where(AuditLog.action == 'report.export')
                                    .order_by(AuditLog.id.desc())).all()
        self.assertTrue(audit_rows)
        self.assertEqual(audit_rows[0].user_id, account['id'])
        self.assertEqual((audit_rows[0].detail or {}).get('days'), 30)

    # -------------------------------------- 数据版本审核与发布（M3-05）
    def version_row(self, current=False, review_status='pending', dataset='测试数据集'):
        with SessionLocal() as db:
            version = DataVersion(
                dataset=dataset, province='浙江', exam_year=2026,
                source_url='https://example.edu.cn/notice', fetched_at='2026-11-13T00:00:00+08:00',
                content_sha256='a' * 64, parser_version='test@1.0.0', doc_status='已导入',
                is_current=current, review_status=review_status, row_count=10,
            )
            db.add(version)
            db.commit()
            db.refresh(version)
            return version.id

    def test_data_version_review_publish_and_audit(self):
        candidate = self.register('普通考生')
        admin = self.register('管理员')
        old_id = self.version_row(current=True, review_status='approved')
        new_id = self.version_row(current=False)

        self.assertEqual(self.client.get('/api/ops/data-versions').status_code, 401)
        with self.admin_mode(None):
            self.assertEqual(self.client.get('/api/ops/data-versions',
                                             headers=candidate['headers']).status_code, 403)
        with self.admin_mode(admin['email']):
            listing = self.client.get('/api/ops/data-versions', headers=admin['headers'])
            self.assertEqual(listing.status_code, 200, listing.text)
            data = listing.json()
            for key in ('total', 'counts', 'current', 'items', 'note'):
                self.assertIn(key, data)
            self.assertGreaterEqual(data['counts']['pending'], 1)
            self.assertEqual(self.client.get('/api/ops/data-versions', params={'status': 'x'},
                                             headers=admin['headers']).status_code, 422)

            rejected = self.client.post(f'/api/ops/data-versions/{new_id}/review',
                                        json={'decision': 'rejected', 'note': '来源不符'},
                                        headers=admin['headers'])
            self.assertEqual(rejected.status_code, 200, rejected.text)
            self.assertEqual(rejected.json()['review_status'], 'rejected')
            self.assertFalse(rejected.json()['is_current'])

            approved = self.client.post(f'/api/ops/data-versions/{new_id}/review',
                                        json={'decision': 'approved', 'note': '已核对公告'},
                                        headers=admin['headers'])
            self.assertEqual(approved.status_code, 200, approved.text)
            body = approved.json()
            self.assertEqual(body['review_status'], 'approved')
            self.assertTrue(body['is_current'])
            self.assertEqual(body['reviewed_by'], admin['email'])
            self.assertTrue(body['reviewed_at'])

            self.assertEqual(self.client.post('/api/ops/data-versions/999999/review',
                                              json={'decision': 'approved'},
                                              headers=admin['headers']).status_code, 404)
            self.assertEqual(self.client.post(f'/api/ops/data-versions/{new_id}/review',
                                              json={'decision': 'unknown'},
                                              headers=admin['headers']).status_code, 422)

        with SessionLocal() as db:
            old = db.get(DataVersion, old_id)
            new = db.get(DataVersion, new_id)
            self.assertFalse(old.is_current)
            self.assertTrue(new.is_current)
            audit_row = db.scalars(select(AuditLog).where(
                AuditLog.action == 'data_version.review').order_by(AuditLog.id.desc())).first()
            self.assertIsNotNone(audit_row)
            self.assertEqual(audit_row.user_id, admin['id'])

    # -------------------------------------- 系统配置与权限审计（M10-05 / M10-03）
    def test_admin_system_config_masks_secrets(self):
        candidate = self.register('普通考生')
        admin = self.register('管理员')
        self.assertEqual(self.client.get('/api/ops/system-config').status_code, 401)
        with self.admin_mode(None):
            self.assertEqual(self.client.get('/api/ops/system-config',
                                             headers=candidate['headers']).status_code, 403)
        with self.admin_mode(admin['email']):
            response = self.client.get('/api/ops/system-config', headers=admin['headers'])
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        for key in ('app', 'database', 'security', 'ai', 'map', 'note'):
            self.assertIn(key, data)
        self.assertEqual(data['app']['name'], 'SunPath 阳光志愿')
        self.assertIn(data['database']['backend'], {'SQLite', 'mysql', 'unknown'})
        self.assertIn('jwt_expire_minutes', data['security'])
        self.assertIn('provider', data['ai'])
        self.assertIn('provider', data['map'])
        self.assertNotIn('jwt_secret', response.text)
        self.assertNotIn('deepseek_api_key', response.text)
        self.assertNotIn('password', response.text.lower())

    def test_admin_permission_audit_masks_emails(self):
        candidate = self.register('普通考生')
        admin = self.register('管理员')
        with SessionLocal() as db:
            db.add(AuditLog(user_id=candidate['id'], action='auth.login', target=f'user:{candidate["id"]}'))
            db.add(AuditLog(user_id=admin['id'], action='data_version.review', target='version:1',
                            detail={'decision': 'approved'}))
            db.commit()
        self.assertEqual(self.client.get('/api/ops/permissions').status_code, 401)
        with self.admin_mode(None):
            self.assertEqual(self.client.get('/api/ops/permissions',
                                             headers=candidate['headers']).status_code, 403)
        with self.admin_mode(admin['email']):
            response = self.client.get('/api/ops/permissions', headers=admin['headers'])
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        for key in ('users', 'admins', 'recent_logins', 'admin_actions', 'denied_count', 'note'):
            self.assertIn(key, data)
        self.assertGreaterEqual(data['users']['total'], 2)
        self.assertEqual(data['users']['total'], data['users']['admins'] + data['users']['candidates'])
        emails = [item['email'] for item in data['admins']]
        emails += [item['email'] for item in data['recent_logins']]
        emails += [item['email'] for item in data['admin_actions']]
        self.assertTrue(emails)
        for masked in emails:
            self.assertIn('***', masked)
            self.assertNotIn(candidate['email'], masked)
            self.assertNotIn(admin['email'], masked)
        self.assertNotIn('password', response.text.lower())


if __name__ == '__main__':
    unittest.main()
