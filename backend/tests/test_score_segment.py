# -*- coding: utf-8 -*-
"""M4-02 一分一段：示例数据文件自检 + 查询服务 + API + 导入脚本 的自动化测试。

沿用 ``tests/test_workflow.py`` 的临时库模式（先 import 它来设置临时 DATABASE_URL），
因此不会读写开发库 ``backend/sunpath.db``。
"""
import json
import os
import secrets
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import test_workflow  # noqa: F401  先设置临时 DATABASE_URL，避免污染开发库
except ImportError:
    from tests import test_workflow  # noqa: F401

from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app
from app.services import score_segment

BACKEND_DIR = Path(__file__).resolve().parents[1]
IMPORT_SCRIPT = BACKEND_DIR / 'scripts' / 'import_score_segment.py'
DATA_FILE = BACKEND_DIR / 'app' / 'data' / 'score_segments.json'
PROVINCE = '浙江'
YEAR = 2026
TOTAL_CANDIDATES = 300000


class DataFileTests(unittest.TestCase):
    """示例数据文件自检：结构、区间、单调性、示例标识与文案边界。"""

    def test_meta_marks_example_data(self):
        meta = score_segment.meta()
        self.assertEqual(meta.get('data_mode'), '示例')
        self.assertIn('官方', meta.get('note', ''))
        self.assertIn('替换', meta.get('note', ''))
        self.assertEqual(meta.get('updated_at'), '2026-11')

    def test_example_data_shape(self):
        entry = score_segment.dataset(PROVINCE, YEAR)
        self.assertIsNotNone(entry)
        self.assertEqual(entry['subject_type'], '综合改革')
        self.assertEqual(entry['total_candidates'], TOTAL_CANDIDATES)
        segments = entry['segments']
        self.assertEqual(segments[0], {'score': 680, 'cumulative': 45, 'count': 12})
        self.assertEqual(segments[-1]['score'], 600)
        self.assertEqual(segments[-1]['cumulative'], 12345)
        self.assertEqual(segments[-1]['count'], 210)
        for previous, current in zip(segments, segments[1:]):
            self.assertEqual(previous['score'] - current['score'], 1)
            self.assertGreater(current['cumulative'], previous['cumulative'])
            self.assertGreater(current['count'], 0)

    def test_data_file_copy_has_no_probability_claim(self):
        text = DATA_FILE.read_text(encoding='utf-8')
        self.assertNotIn('概率', text)
        self.assertNotIn('百分比录取', text)
        self.assertIn('位次参考', text)


class ServiceTests(unittest.TestCase):
    """服务层：命中/边界/未收录/percentile/分段列表。"""

    def test_query_hit_returns_expected_fields(self):
        result = score_segment.query(PROVINCE, YEAR, 628)
        self.assertIsNotNone(result)
        for field in ('province', 'exam_year', 'subject_type', 'score', 'count', 'cumulative',
                      'rank_estimate', 'percentile', 'source_url', 'published_at', 'data_mode', 'note'):
            self.assertIn(field, result)
        self.assertEqual(result['province'], PROVINCE)
        self.assertEqual(result['exam_year'], YEAR)
        self.assertEqual(result['subject_type'], '综合改革')
        self.assertEqual(result['score'], 628)
        self.assertIsInstance(result['count'], int)
        self.assertIsInstance(result['cumulative'], int)
        self.assertEqual(result['rank_estimate'], result['cumulative'])
        self.assertEqual(result['total_candidates'], TOTAL_CANDIDATES)
        self.assertEqual(result['percentile'], round(result['cumulative'] / TOTAL_CANDIDATES, 2))
        self.assertGreaterEqual(result['percentile'], 0)
        self.assertLessEqual(result['percentile'], 1)
        self.assertEqual(result['source_url'], 'https://www.zjzs.net/')
        self.assertEqual(result['published_at'], '2026-06-25')
        self.assertEqual(result['data_mode'], '示例')
        self.assertIn('示例数据', result['note'])

    def test_query_boundaries(self):
        top = score_segment.query(PROVINCE, YEAR, 680)
        self.assertEqual((top['score'], top['count'], top['cumulative']), (680, 12, 45))
        bottom = score_segment.query(PROVINCE, YEAR, 600)
        self.assertEqual((bottom['score'], bottom['count'], bottom['cumulative']), (600, 210, 12345))
        self.assertEqual(bottom['percentile'], round(12345 / TOTAL_CANDIDATES, 2))

    def test_query_out_of_range_returns_none(self):
        for score in (599, 681, 0, 750):
            self.assertIsNone(score_segment.query(PROVINCE, YEAR, score), score)

    def test_query_unknown_province_or_year_returns_none(self):
        self.assertIsNone(score_segment.query('火星', YEAR, 600))
        self.assertIsNone(score_segment.query(PROVINCE, 2025, 600))

    def test_segments_limit_order_and_provenance(self):
        result = score_segment.segments(PROVINCE, YEAR, 5)
        self.assertEqual(result['total'], 5)
        self.assertEqual(len(result['segments']), 5)
        self.assertEqual(result['direction'], 'desc')
        scores = [item['score'] for item in result['segments']]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(scores[0], 680)
        self.assertEqual(result['subject_type'], '综合改革')
        self.assertEqual(result['source_url'], 'https://www.zjzs.net/')
        self.assertEqual(result['published_at'], '2026-06-25')
        self.assertEqual(result['data_mode'], '示例')
        self.assertIn('示例数据', result['note'])

        everything = score_segment.segments(PROVINCE, YEAR, 200)
        self.assertEqual(len(everything['segments']), 81)
        self.assertEqual(everything['segments'][-1]['score'], 600)

    def test_segments_unknown_returns_none(self):
        self.assertIsNone(score_segment.segments('火星', YEAR, 10))
        self.assertIsNone(score_segment.segments(PROVINCE, 2025, 10))


class ApiTests(unittest.TestCase):
    """REST 层：登录依赖、200/404 文案、参数校验、segments limit。"""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(engine)
        cls.client = TestClient(app)
        response = cls.client.post('/api/auth/register', json={
            'email': f'score-segment-{secrets.token_hex(4)}@test.cn',
            'password': 'TestPassword123!',
            'name': '一分一段测试',
        })
        assert response.status_code == 201, response.text
        cls.headers = {'Authorization': f"Bearer {response.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()  # 释放临时库文件句柄，避免 test_workflow 的临时目录清理报占用

    def url(self, suffix=''):
        return '/api/score-segment' + suffix

    def test_requires_login(self):
        self.assertEqual(
            self.client.get(self.url(), params={'province': PROVINCE, 'year': YEAR, 'score': 628}).status_code, 401)
        self.assertEqual(
            self.client.get(self.url('/segments'), params={'province': PROVINCE, 'year': YEAR}).status_code, 401)

    def test_query_hit(self):
        response = self.client.get(self.url(), params={'province': PROVINCE, 'year': YEAR, 'score': 628},
                                   headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['score'], 628)
        self.assertEqual(data['exam_year'], YEAR)
        self.assertEqual(data['data_mode'], '示例')
        self.assertIn('位次参考', data['disclaimer'])
        self.assertNotIn('概率', response.text)
        self.assertEqual(data['percentile'], round(data['cumulative'] / data['total_candidates'], 2))

    def test_query_404_messages(self):
        low = self.client.get(self.url(), params={'province': PROVINCE, 'year': YEAR, 'score': 599},
                              headers=self.headers)
        self.assertEqual(low.status_code, 404)
        self.assertEqual(low.json()['detail'], '该分数段未收录')

        unknown_province = self.client.get(self.url(), params={'province': '火星', 'year': YEAR, 'score': 600},
                                           headers=self.headers)
        self.assertEqual(unknown_province.status_code, 404)
        self.assertEqual(unknown_province.json()['detail'], '该省未收录一分一段数据')

        unknown_year = self.client.get(self.url(), params={'province': PROVINCE, 'year': 2025, 'score': 600},
                                       headers=self.headers)
        self.assertEqual(unknown_year.status_code, 404)
        self.assertEqual(unknown_year.json()['detail'], '该省未收录一分一段数据')

    def test_query_validation(self):
        cases = [
            {'province': PROVINCE, 'year': YEAR},                     # 缺 score
            {'province': PROVINCE, 'year': YEAR, 'score': 751},       # 超上限
            {'province': PROVINCE, 'year': YEAR, 'score': -1},        # 低于下限
            {'province': '浙', 'year': YEAR, 'score': 628},           # 省份过短
            {'province': PROVINCE, 'score': 628},                     # 缺 year
            {'year': YEAR, 'score': 628},                             # 缺 province
            {'province': PROVINCE, 'year': 1999, 'score': 628},       # 年份越界
        ]
        for params in cases:
            self.assertEqual(self.client.get(self.url(), params=params, headers=self.headers).status_code,
                             422, params)

    def test_segments_hit_limit_and_validation(self):
        response = self.client.get(self.url('/segments'), params={'province': PROVINCE, 'year': YEAR, 'limit': 60},
                                   headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(len(data['segments']), 60)
        self.assertEqual(data['segments'][0]['score'], 680)
        self.assertEqual(data['direction'], 'desc')
        self.assertEqual(data['data_mode'], '示例')
        self.assertIn('位次参考', data['disclaimer'])
        self.assertNotIn('概率', response.text)

        for limit in (0, 201):
            self.assertEqual(
                self.client.get(self.url('/segments'),
                                params={'province': PROVINCE, 'year': YEAR, 'limit': limit},
                                headers=self.headers).status_code, 422, limit)

        unknown = self.client.get(self.url('/segments'), params={'province': '火星', 'year': YEAR},
                                  headers=self.headers)
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(unknown.json()['detail'], '该省未收录一分一段数据')


class ImportScriptTests(unittest.TestCase):
    """导入脚本：CSV → JSON、幂等覆盖、非法数据非 0 退出、导入结果可被服务层读取。"""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix='sunpath-segment-')
        self.tmp = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def _write_csv(self, rows, name='segments.csv'):
        path = self.tmp / name
        lines = ['分数,人数,累计人数'] + [f'{score},{count},{cumulative}' for score, count, cumulative in rows]
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8-sig')  # 带 BOM 的 CSV
        return path

    def _run(self, *args):
        env = dict(os.environ)
        env['PYTHONPATH'] = str(BACKEND_DIR)
        env['PYTHONIOENCODING'] = 'utf-8'
        env['TMP'] = str(self.tmp)
        env['TEMP'] = str(self.tmp)
        return subprocess.run(
            [sys.executable, str(IMPORT_SCRIPT), *args],
            cwd=str(BACKEND_DIR), env=env, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=120,
        )

    def test_import_is_idempotent_and_service_can_read_it(self):
        csv_path = self._write_csv([(680, 12, 45), (679, 30, 75), (678, 31, 106)])
        data_file = self.tmp / 'segments.json'
        args = [
            '--province', '测试省', '--year', '2026', '--subject-type', '综合改革',
            '--source-url', 'https://example.gov.cn/one-score-one-rank',
            '--published-at', '2026-06-25', '--csv', str(csv_path),
            '--data-file', str(data_file),
        ]
        first = self._run(*args)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn('segments 3 条', first.stdout)
        self.assertIn('新增', first.stdout)
        payload = json.loads(data_file.read_text(encoding='utf-8'))
        self.assertEqual(payload['_meta']['data_mode'], '示例')
        self.assertIn('替换', payload['_meta']['note'])
        entry = payload['provinces']['测试省']['2026']
        self.assertEqual(entry['subject_type'], '综合改革')
        self.assertEqual(entry['source_url'], 'https://example.gov.cn/one-score-one-rank')
        self.assertEqual(entry['published_at'], '2026-06-25')
        self.assertEqual(entry['total_candidates'], 106)
        self.assertEqual(len(entry['segments']), 3)
        first_bytes = data_file.read_bytes()

        second = self._run(*args)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn('已覆盖', second.stdout)
        self.assertEqual(data_file.read_bytes(), first_bytes, '同省同年重复导入应幂等（文件字节一致）')

        # 不改动仓库内示例数据：临时 monkeypatch DATA_FILE 后验证服务层能读取导入文件
        original_data_file = score_segment.DATA_FILE
        score_segment.DATA_FILE = data_file
        score_segment.load_data.cache_clear()
        try:
            hit = score_segment.query('测试省', 2026, 679)
            self.assertIsNotNone(hit)
            self.assertEqual(hit['cumulative'], 75)
            self.assertEqual(hit['count'], 30)
            self.assertEqual(hit['percentile'], round(75 / 106, 2))
            self.assertEqual(hit['data_mode'], '示例')
            listed = score_segment.segments('测试省', 2026, 2)
            self.assertEqual([item['score'] for item in listed['segments']], [680, 679])
        finally:
            score_segment.DATA_FILE = original_data_file
            score_segment.load_data.cache_clear()

    def test_invalid_csv_exits_nonzero_without_writing(self):
        cases = {
            'desc.csv': [(680, 12, 45), (681, 30, 75)],        # 分数未严格降序
            'cumulative.csv': [(680, 12, 45), (679, 30, 44)],  # 累计人数未严格递增
            'zero.csv': [(680, 0, 45), (679, 30, 75)],         # 人数非正
        }
        for name, rows in cases.items():
            csv_path = self._write_csv(rows, name=name)
            data_file = self.tmp / (name + '.json')
            result = self._run('--province', '测试省', '--year', '2026', '--subject-type', '综合改革',
                               '--csv', str(csv_path), '--data-file', str(data_file))
            self.assertNotEqual(result.returncode, 0, name)
            self.assertIn('[ERROR]', result.stderr, name)
            self.assertFalse(data_file.exists(), name)

    def test_overlong_scores_rejected(self):
        csv_path = self._write_csv([(751, 12, 45), (750, 30, 75)])
        data_file = self.tmp / 'bad-score.json'
        result = self._run('--province', '测试省', '--year', '2026', '--subject-type', '综合改革',
                           '--csv', str(csv_path), '--data-file', str(data_file))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('分数越界', result.stderr)
        self.assertFalse(data_file.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
