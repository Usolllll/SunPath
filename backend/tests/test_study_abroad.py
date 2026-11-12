"""留学规划（M11）后端隔离测试：官方入口索引 + 个人路径目标 + 语言三态。

复用 test_workflow 的临时库模式（先 ``import test_workflow`` 让它在导入 app 前设置 DATABASE_URL），
不连开发库、不依赖本机 .env；只读真实的 app/data/study_abroad.json（18 所学校）。

运行（backend 目录下）：
    ..\\..\\Python311\\python.exe -m unittest tests.test_study_abroad -v
"""
import copy
import json
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

from app.core.database import SessionLocal, engine
from app.main import app
from app.models.entities import StudyAbroadTarget
from app.seed import seed
from app.services import study_abroad as study_service

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = BACKEND_DIR / 'app' / 'data' / 'study_abroad.json'
DATA = json.loads(DATA_FILE.read_text(encoding='utf-8'))
DISCLAIMER = '申请要求与截止日期以学校官网为准，本模块只做官方入口索引，不代填申请表。'
BASE_TARGET = {'region': 'UK', 'school_id': 'uk-imperial', 'test_type': 'ielts',
               'test_score': 7.0, 'target_major': '计算机科学'}
URL = '/api/study-abroad'


def schools_of(payload: dict) -> list[dict]:
    return [school for region in payload['regions'] for school in region['schools']]


class StudyAbroadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()

    def setUp(self):
        self.user, self.headers = self.account()

    # ---------------------------------------------------------------- helpers
    def account(self):
        email = f'{secrets.token_hex(8)}@test.cn'
        response = self.client.post('/api/auth/register',
                                    json={'email': email, 'password': 'TestPassword123!', 'name': '留学测试'})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['user'], {'Authorization': f"Bearer {response.json()['access_token']}"}

    def target(self, headers=None):
        response = self.client.get(f'{URL}/target', headers=headers or self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def save(self, **changes):
        response = self.client.put(f'{URL}/target', headers=self.headers, json={**BASE_TARGET, **changes})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def audit(self):
        response = self.client.get('/api/ops/audit', headers=self.headers, params={'limit': 100})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['items']

    def find_school(self, payload, school_id):
        return next(school for school in schools_of(payload) if school['id'] == school_id)

    # ---------------------------------------------------------------- 选项
    def test_options_structure_and_auth(self):
        for method, path in [('get', f'{URL}/options'), ('get', f'{URL}/target'),
                             ('put', f'{URL}/target'), ('delete', f'{URL}/target')]:
            self.assertEqual(getattr(self.client, method)(path).status_code, 401)

        payload = self.client.get(f'{URL}/options', headers=self.headers).json()
        self.assertEqual(payload['disclaimer'], DISCLAIMER)
        self.assertEqual({test['code'] for test in payload['tests']}, {'ielts', 'toefl'})
        self.assertEqual(len(payload['regions']), 4)
        self.assertEqual({region['code'] for region in payload['regions']}, {'UK', 'HK', 'US', 'SG'})
        schools = schools_of(payload)
        self.assertEqual(len(schools), 18)
        self.assertEqual(len(schools), sum(len(region['schools']) for region in DATA['regions']))
        for school in schools:
            self.assertTrue(school['official_url'].startswith('https://'), school['id'])
            self.assertTrue(school['qualifications'], school['id'])
            self.assertIsInstance(school['gaokao']['accepted'], bool, school['id'])
        for region in payload['regions']:
            self.assertEqual(set(region['pathways']), {'gaokao', 'post_gaokao', 'international'})
            self.assertIsInstance(region['gaokao']['accepted'], bool)
        pathways = payload['meta']['pathways']
        self.assertEqual({item['code'] for item in pathways}, {'gaokao', 'post_gaokao', 'international'})

    # ---------------------------------------------------------------- 初始状态
    def test_initial_target_is_null(self):
        payload = self.target()
        self.assertIsNone(payload['target'])
        self.assertIsNone(payload['plan'])
        self.assertEqual(payload['disclaimer'], DISCLAIMER)

    # ---------------------------------------------------------------- 保存（高考路径）
    def test_save_gaokao_target_plan_and_audit(self):
        payload = self.save()  # path 缺省 = gaokao
        target, plan = payload['target'], payload['plan']
        self.assertEqual(target['region'], 'UK')
        self.assertEqual(target['region_label'], '英国')
        self.assertEqual(target['school_id'], 'uk-imperial')
        self.assertEqual(target['school_name'], 'Imperial College London')
        self.assertEqual(target['school_name_zh'], '帝国理工学院')
        self.assertEqual(target['test_type'], 'ielts')
        self.assertEqual(target['test_label'], '雅思 IELTS')
        self.assertEqual(target['test_score'], 7.0)
        self.assertEqual(target['target_major'], '计算机科学')
        self.assertEqual(target['path'], 'gaokao')
        self.assertIn('高考', target['path_label'])
        self.assertIsNone(target['gaokao_score'])
        self.assertIsNotNone(target['saved_at'])

        self.assertEqual(plan['school']['official_url'], 'https://www.imperial.ac.uk/study/apply/undergraduate/')
        self.assertEqual(plan['school']['intakes'], ['每年 10 月'])
        self.assertIn('入学考试', plan['school']['note'])
        self.assertIn('A-Level', plan['school']['qualifications'])
        language = plan['language']
        self.assertEqual(language['status'], 'reached')
        self.assertEqual(language['label'], '达到参考最低语言要求')
        self.assertEqual(language['required'], 6.5)
        self.assertEqual(language['user_score'], 7.0)
        self.assertEqual(language['scale'], '0–9 分')
        self.assertEqual(plan['pathway']['code'], 'gaokao')
        self.assertTrue(plan['pathway']['summary'])
        self.assertIn('英国', plan['pathway']['region_note'])
        self.assertIs(plan['gaokao']['accepted'], False)
        self.assertEqual(plan['gaokao']['label'], '参考：通常不接受高考成绩直申')
        self.assertEqual(plan['path_warning'],
                         '该校通常不接受高考成绩直申，建议考虑预科/国际课程路径，具体以官网为准')
        self.assertEqual([link['label'] for link in plan['links']],
                         ['学校官方申请入口', '本地区申请平台/说明', '考试官方报名入口'])
        self.assertEqual(len({link['url'] for link in plan['links']}), 3)
        checklist = {item['key']: item for item in plan['checklist']}
        self.assertIn('gaokao_score', checklist)
        self.assertIn('高考成绩单/省排名证明', checklist['gaokao_score']['label'])
        self.assertIn('language', checklist)
        self.assertEqual(len(plan['checklist']), 9)
        self.assertEqual(len(plan['timeline']), 5)
        self.assertTrue(all({'stage', 'when', 'detail'} <= set(item) for item in plan['timeline']))

        # 持久化：重新 GET 一致
        self.assertEqual(self.target(), payload)
        updates = [item for item in self.audit() if item['action'] == 'study_abroad.save']
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]['detail'],
                         {'region': 'UK', 'school_id': 'uk-imperial', 'test_type': 'ielts'})

    def test_gaokao_labels_for_hk_and_sg(self):
        for region, school_id, test_type, score in (
            ('HK', 'hk-hku', 'ielts', 6.5),
            ('SG', 'sg-nus', 'toefl', 100),
        ):
            payload = self.save(region=region, school_id=school_id, test_type=test_type, test_score=score)
            self.assertIs(payload['plan']['gaokao']['accepted'], True)
            self.assertEqual(payload['plan']['gaokao']['label'], '参考：接受高考成绩直申')
            self.assertEqual(payload['plan']['path_warning'], '')

    # ---------------------------------------------------------------- 三条路径
    def test_path_variants_checklist_and_timeline(self):
        post = self.save(region='UK', school_id='uk-manchester', test_score=6.5, path='post_gaokao')
        self.assertEqual(post['target']['path'], 'post_gaokao')
        self.assertIn('预科', post['target']['path_label'])
        self.assertEqual(post['plan']['pathway']['code'], 'post_gaokao')
        post_keys = {item['key'] for item in post['plan']['checklist']}
        self.assertIn('foundation', post_keys)
        foundation = next(item for item in post['plan']['checklist'] if item['key'] == 'foundation')
        self.assertIn('预科/国际大一', foundation['label'])
        self.assertEqual(post['plan']['timeline'][0]['when'], '高考出分后 1–3 个月内')
        self.assertEqual(post['plan']['path_warning'], '')

        international = self.save(region='US', school_id='us-mit', test_type='toefl', test_score=100,
                                  path='international')
        self.assertIn('国际课程', international['target']['path_label'])
        intl_keys = {item['key'] for item in international['plan']['checklist']}
        self.assertIn('international_curriculum', intl_keys)
        curriculum = next(item for item in international['plan']['checklist']
                          if item['key'] == 'international_curriculum')
        self.assertIn('国际课程成绩单（A-Level/IB/AP）', curriculum['label'])
        self.assertEqual(international['plan']['timeline'][0]['when'], '提前 18–24 个月')
        self.assertEqual(international['plan']['pathway']['code'], 'international')

    # ---------------------------------------------------------------- 语言三态
    def test_language_below_unknown_and_rounding(self):
        below = self.save(test_score=6.0)
        self.assertEqual(below['plan']['language']['status'], 'below')
        self.assertEqual(below['plan']['language']['label'], '低于参考最低语言要求')
        self.assertEqual(below['plan']['language']['required'], 6.5)

        rounded = self.save(test_score=7.456)
        self.assertEqual(rounded['target']['test_score'], 7.5)
        self.assertEqual(rounded['plan']['language']['user_score'], 7.5)
        self.assertEqual(rounded['plan']['language']['status'], 'reached')

        # 临时把 uk-ucl 的语言要求改为缺失 → unknown（不修改真实数据文件）
        data = copy.deepcopy(study_service.load_data())
        region = next(item for item in data['regions'] if item['code'] == 'UK')
        ucl = next(school for school in region['schools'] if school['id'] == 'uk-ucl')
        ucl['language'] = {}
        with patch('app.services.study_abroad.load_data', return_value=data):
            unknown = self.save(region='UK', school_id='uk-ucl', test_score=8.0, path='gaokao')
        self.assertIsNone(unknown['plan']['language']['required'])
        self.assertEqual(unknown['plan']['language']['status'], 'unknown')
        self.assertEqual(unknown['plan']['language']['label'], '暂无参考语言要求，请查官网')

    # ---------------------------------------------------------------- 校验
    def test_validation_errors(self):
        cases = [
            ({**BASE_TARGET, 'region': 'XX'}, 400, '未收录'),
            ({**BASE_TARGET, 'school_id': 'us-mit'}, 400, '不属于'),
            ({**BASE_TARGET, 'school_id': 'no-such-school'}, 400, '不属于'),
            ({**BASE_TARGET, 'test_score': 9.5}, 400, '0–9'),
            ({**BASE_TARGET, 'test_score': -1}, 400, '0–9'),
            ({**BASE_TARGET, 'region': 'SG', 'school_id': 'sg-nus',
              'test_type': 'toefl', 'test_score': 130}, 400, '0–120'),
            ({**BASE_TARGET, 'gaokao_score': 751}, 400, '0–750'),
            ({**BASE_TARGET, 'gaokao_score': -1}, 400, '0–750'),
            ({**BASE_TARGET, 'target_major': 'x' * 61}, 400, '60'),
            ({**BASE_TARGET, 'path': 'exchange'}, 422, None),
            ({**BASE_TARGET, 'test_type': 'gre'}, 422, None),
            ({**BASE_TARGET, 'test_score': 'abc'}, 422, None),
            ({**BASE_TARGET, 'gaokao_score': 'abc'}, 422, None),
        ]
        for body, expected, message in cases:
            response = self.client.put(f'{URL}/target', headers=self.headers, json=body)
            self.assertEqual(response.status_code, expected, (body, response.text))
            if message:
                self.assertIn(message, response.json()['detail'])
        missing_region = {key: value for key, value in BASE_TARGET.items() if key != 'region'}
        self.assertEqual(self.client.put(f'{URL}/target', headers=self.headers,
                                         json=missing_region).status_code, 422)
        # 全部失败后仍没有保存任何目标
        self.assertIsNone(self.target()['target'])

    # ---------------------------------------------------------------- upsert 与删除
    def test_upsert_keeps_single_target_and_delete_clears(self):
        self.save()
        self.save(region='HK', school_id='hk-hku', test_score=6.5)
        with SessionLocal() as db:
            rows = db.scalars(select(StudyAbroadTarget)
                              .where(StudyAbroadTarget.user_id == self.user['id'])).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].school_id, 'hk-hku')
        self.assertEqual(self.target()['target']['school_id'], 'hk-hku')

        self.assertEqual(self.client.delete(f'{URL}/target', headers=self.headers).status_code, 204)
        cleared = self.target()
        self.assertIsNone(cleared['target'])
        self.assertIsNone(cleared['plan'])
        self.assertEqual(self.client.delete(f'{URL}/target', headers=self.headers).status_code, 204)
        clears = [item for item in self.audit() if item['action'] == 'study_abroad.clear']
        self.assertEqual(len(clears), 2)
        self.assertEqual(clears[0]['detail'], {'existed': False})
        self.assertEqual(clears[1]['detail'], {'existed': True})

    # ---------------------------------------------------------------- 迁移幂等
    def test_migrate_v6_is_idempotent(self):
        script = BACKEND_DIR / 'scripts' / 'migrate_v6.py'
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / 'migrate_v6.db'
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
            for output in outputs:
                self.assertIn('study_abroad_targets 共 0 行', output)
            connection = sqlite3.connect(db_path)
            try:
                columns = [row[1] for row in connection.execute('PRAGMA table_info(study_abroad_targets)')]
                rows = connection.execute('SELECT COUNT(*) FROM study_abroad_targets').fetchone()[0]
            finally:
                connection.close()
            for column in ('user_id', 'region', 'school_id', 'test_type', 'test_score',
                           'target_major', 'path', 'gaokao_score', 'created_at', 'updated_at'):
                self.assertIn(column, columns)
            self.assertEqual(rows, 0)


if __name__ == '__main__':
    unittest.main()
