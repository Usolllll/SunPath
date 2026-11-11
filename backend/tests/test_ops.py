"""运营治理接口测试：FAQ / 数据字典 / 质量看板 / 审计 / 热度 / 备份恢复 / 画像完整度。

复用 test_workflow 的临时 SQLite 模式（先 import 设置 DATABASE_URL），不连开发库。
"""
import hashlib
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

try:
    import test_workflow  # noqa: F401  先设置临时 DATABASE_URL，避免污染开发库
except ImportError:
    from tests import test_workflow  # noqa: F401

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal, engine
from app.main import app
from app.models.entities import AuditLog, Favorite, Profile, University
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
        self.assertEqual(simulated['enrollments'], 60 * 2 * len(PROVINCES))
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


if __name__ == '__main__':
    unittest.main()
