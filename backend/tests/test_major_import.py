# -*- coding: utf-8 -*-
"""import_major_csv.py（专业级追加导入）+ real_data 院校级聚合的自动化测试。

沿用 ``tests/test_workflow.py`` 的临时库模式（先 import 它来设置临时 DATABASE_URL）；
CLI 用例都通过 --database-url 指向 tempdir 下的临时 SQLite，不读写开发库。
"""
import csv
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import test_workflow  # noqa: F401  先设置临时 DATABASE_URL，避免污染开发库
except ImportError:
    from tests import test_workflow  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import RealAdmission
from app.services import real_data

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND_DIR / 'scripts' / 'import_major_csv.py'

HEADER = ['学校名称', '全国院校代码', '生源省份', '招生年份', '招考科类', '招生类型', '投档轮次',
          '专业组代号', '专业组名称', '具体专业', '最低分', '最低位次', '最高分', '平均分',
          '实际录取人数', '选科要求', '来源链接', '备注']
HEADER_17 = [column for column in HEADER if column != '选科要求']
BASE = dict(zip(HEADER, [
    '测试大学', '10284', '安徽', '2026', '物理类', '普通类', '本科批',
    '001', '测试大学物理类第001组', '计算机科学与技术', '650', '1200', '660', '655',
    '3', '物理,化学', 'https://example.edu.cn/c/2026-07-25/1.html', '测试备注',
]))


def make_row(**overrides):
    row = dict(BASE)
    row.update(overrides)
    return row


def write_csv(path: Path, rows, header=None) -> None:
    header = header or HEADER
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row in rows:
            writer.writerow([row.get(column, '') for column in header])


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MajorImportCliTests(unittest.TestCase):
    """subprocess 跑真实 CLI，对临时 SQLite 断言。"""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix='sunpath-major-import-')
        self.tmp = Path(self.tempdir.name)
        self.db_path = self.tmp / 'test.db'
        self.database_url = 'sqlite:///' + self.db_path.as_posix()
        self.report_index = 0

    def tearDown(self):
        self.tempdir.cleanup()

    # ------------------------------------------------------------------ 工具
    def run_cli(self, *args, expect_ok=True):
        env = dict(os.environ)
        env.pop('DATABASE_URL', None)
        env['PYTHONPATH'] = str(BACKEND_DIR)
        env['PYTHONIOENCODING'] = 'utf-8'
        env['TMP'] = str(self.tmp)
        env['TEMP'] = str(self.tmp)
        self.report_index += 1
        report_path = self.tmp / f'report-{self.report_index}.json'
        command = [sys.executable, str(SCRIPT), '--database-url', self.database_url,
                   '--json-report', str(report_path), *args]
        process = subprocess.run(command, cwd=str(BACKEND_DIR), env=env, capture_output=True,
                                 text=True, encoding='utf-8', errors='replace', timeout=180)
        if expect_ok:
            self.assertEqual(process.returncode, 0,
                             f'CLI 失败：\nSTDOUT:\n{process.stdout}\nSTDERR:\n{process.stderr}')
        payload = json.loads(report_path.read_text(encoding='utf-8')) if report_path.is_file() else None
        return process, payload

    def query(self, sql, params=()):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            return connection.execute(sql, params).fetchall()
        finally:
            connection.close()

    def count(self, table):
        return self.query(f'SELECT COUNT(*) AS n FROM {table}')[0]['n']

    # ------------------------------------------------------------------ 用例
    def test_column_mapping_provenance_and_17_column_file(self):
        csv_path = self.tmp / '985_测试_招生计划.csv'
        write_csv(csv_path, [make_row(学校名称='A442测试大学')])
        _, report = self.run_cli('--csv', str(csv_path))
        file_stats = report['files'][0]
        self.assertEqual(file_stats['parsed'], 1)
        self.assertEqual(file_stats['inserted'], 1)
        self.assertEqual(file_stats['invalid'], 0)
        self.assertEqual(file_stats['dataset'], '招生计划')

        row = self.query('SELECT * FROM real_admissions')[0]
        self.assertEqual(row['school_name'], '测试大学')          # 去掉了省内代号前缀
        self.assertEqual(row['national_code'], '10284')
        self.assertEqual(row['province'], '安徽')
        self.assertEqual(row['exam_year'], 2026)
        self.assertEqual(row['subject_type'], '物理类')
        self.assertEqual(row['admission_type'], '普通类')
        self.assertEqual(row['round_no'], '本科批')
        self.assertEqual(row['group_code'], '001')
        self.assertEqual(row['group_name'], '测试大学物理类第001组')
        self.assertEqual(row['major_name'], '计算机科学与技术')
        self.assertEqual(row['min_score'], 650)
        self.assertEqual(row['min_rank'], 1200)
        self.assertEqual(row['max_score'], 660)
        self.assertEqual(row['avg_score'], 655)
        self.assertEqual(row['actual_count'], 3)
        self.assertIsNone(row['batch'])
        self.assertIsNone(row['plan_count'])
        self.assertEqual(row['required_subjects'], '物理,化学')
        self.assertEqual(row['source_url'], 'https://example.edu.cn/c/2026-07-25/1.html')
        self.assertEqual(row['published_at'], '2026-07-25')
        self.assertEqual(row['content_sha256'], sha256_of(csv_path))
        self.assertEqual(row['parser_version'], 'major-csv@1.0.0')
        self.assertEqual(row['doc_status'], '已导入')
        self.assertIn('测试备注', row['note'])
        self.assertRegex(row['fetched_at'], r'\+08:00$')

        versions = self.query('SELECT * FROM data_versions')
        self.assertEqual(len(versions), 1)
        version = versions[0]
        self.assertEqual(version['dataset'], '招生计划')
        self.assertEqual(version['province'], '安徽')
        self.assertEqual(version['is_current'], 1)
        self.assertEqual(version['row_count'], 1)
        self.assertEqual(version['content_sha256'], sha256_of(csv_path))
        self.assertEqual(version['parser_version'], 'major-csv@1.0.0')
        self.assertEqual(version['doc_status'], '已导入')
        self.assertEqual(version['source_url'], 'https://example.edu.cn/c/2026-07-25/1.html')
        self.assertEqual(version['published_at'], '2026-07-25')
        self.assertEqual(file_stats['data_version_id'], version['id'])

        # 17 列表头（无「选科要求」）也要能导入，required_subjects 为空
        csv17 = self.tmp / '河北_历史_投档.csv'
        write_csv(csv17, [make_row(生源省份='河北', 招生年份='2024', 招考科类='历史类',
                                   专业组名称='历史组', 具体专业='法学', 选科要求=None)],
                  header=HEADER_17)
        _, report17 = self.run_cli('--csv', str(csv17))
        self.assertEqual(report17['files'][0]['invalid'], 0)
        self.assertEqual(report17['files'][0]['dataset'], '专业级投档')
        row17 = self.query("SELECT * FROM real_admissions WHERE province = '河北'")[0]
        self.assertIsNone(row17['required_subjects'])
        self.assertEqual(row17['exam_year'], 2024)

    def test_same_file_duplicate_and_repeat_run_idempotent(self):
        csv_path = self.tmp / '河北_物理_投档.csv'
        write_csv(csv_path, [
            make_row(生源省份='河北', 专业组名称='计算机组', 具体专业='计算机科学与技术'),
            make_row(生源省份='河北', 专业组名称='计算机组', 具体专业='计算机科学与技术', 最低分='640'),
            make_row(生源省份='河北', 专业组名称='法学组', 具体专业='法学'),
        ])
        _, first = self.run_cli('--csv', str(csv_path))
        stats = first['files'][0]
        self.assertEqual((stats['parsed'], stats['inserted'], stats['skipped_duplicate'],
                          stats['skipped_existing'], stats['invalid']), (3, 2, 1, 0, 0))
        self.assertEqual(self.count('real_admissions'), 2)
        self.assertEqual(self.count('data_versions'), 1)
        first_dv_id = stats['data_version_id']

        _, second = self.run_cli('--csv', str(csv_path))
        stats2 = second['files'][0]
        self.assertEqual((stats2['parsed'], stats2['inserted'], stats2['skipped_duplicate'],
                          stats2['skipped_existing'], stats2['invalid']), (3, 0, 1, 2, 0))
        self.assertEqual(stats2['data_version_id'], first_dv_id, '同文件重复运行应复用 DataVersion')
        self.assertEqual(self.count('real_admissions'), 2)
        self.assertEqual(self.count('data_versions'), 1)
        # 同文件重复只保留首行（最低分 650）
        kept = self.query("SELECT min_score FROM real_admissions WHERE major_name = '计算机科学与技术'")
        self.assertEqual([item['min_score'] for item in kept], [650])

    def test_cross_file_overlap_and_version_rotation(self):
        file_a = self.tmp / '河北_历史_投档_a.csv'
        file_b = self.tmp / '河北_历史_投档_b.csv'
        write_csv(file_a, [
            make_row(生源省份='河北', 招考科类='历史类', 专业组名称='历史组A', 具体专业='历史学'),
            make_row(生源省份='河北', 招考科类='历史类', 专业组名称='历史组B', 具体专业='汉语言文学'),
        ])
        write_csv(file_b, [
            make_row(生源省份='河北', 招考科类='历史类', 专业组名称='历史组A', 具体专业='历史学',
                     最低分='620'),  # 与 file A 唯一键相同 → 跳过
            make_row(生源省份='河北', 招考科类='历史类', 专业组名称='历史组C', 具体专业='新闻学'),
        ])
        _, report = self.run_cli('--csv', str(file_a), '--csv', str(file_b))
        self.assertEqual(report['totals']['parsed'], 4)
        self.assertEqual(report['totals']['inserted'], 3)
        self.assertEqual(report['totals']['skipped_existing'], 1)
        self.assertEqual(self.count('real_admissions'), 3)
        # 两份文件同 dataset+province：后一份把前一份的 is_current 置 False
        versions = self.query('SELECT * FROM data_versions ORDER BY id')
        self.assertEqual(len(versions), 2)
        self.assertEqual(sum(item['is_current'] for item in versions), 1)
        self.assertEqual(versions[-1]['is_current'], 1)

        # 两个文件一起重跑：0 新增，DataVersion 不新增
        _, again = self.run_cli('--csv', str(file_a), '--csv', str(file_b))
        self.assertEqual(again['totals']['inserted'], 0)
        self.assertEqual(again['totals']['skipped_existing'], 4)  # 4 行有效数据都已在库
        self.assertEqual(self.count('real_admissions'), 3)
        self.assertEqual(self.count('data_versions'), 2)

    def test_invalid_rows_rejected_and_aux_score_dropped(self):
        csv_path = self.tmp / '河北_物理_投档_非法.csv'
        write_csv(csv_path, [
            make_row(生源省份='河北', 学校名称=''),                                   # 学校名为空
            make_row(生源省份='河北', 招生年份='1999'),                               # 年份越界
            make_row(生源省份='河北', 最低分='751'),                                  # 最低分越界
            make_row(生源省份='河北', 最低位次='0'),                                  # 位次非正
            make_row(生源省份='河北', 最低位次='abc'),                                # 位次非整数
            make_row(生源省份='安徽'),                                                # 省份与参数不一致
            make_row(生源省份='河北', 招考科类=''),                                   # 科类为空
            make_row(生源省份='河北', 最低分='617.25'),                               # 最低分非整数
            make_row(生源省份='河北', 专业组名称='异常最高分', 最高分='8426'),          # 合法行：最高分置空
            make_row(生源省份='河北', 专业组名称='空分数', 最低分='—', 最低位次='—',
                     最高分='—', 平均分='—'),                                        # 合法行：占位符视为空
        ])
        _, report = self.run_cli('--csv', str(csv_path), '--province', '河北')
        stats = report['files'][0]
        self.assertEqual(stats['parsed'], 10)
        self.assertEqual(stats['inserted'], 2)
        self.assertEqual(stats['invalid'], 8)
        self.assertEqual(stats['invalid_reasons'], {
            '学校名为空': 1, '招生年份越界(2020-2030)': 1, '最低分越界(0-750)': 1,
            '最低位次非正整数': 1, '最低位次非整数': 1, '省份与参数不一致': 1,
            '招考科类为空': 1, '最低分非整数': 1,
        })
        self.assertEqual(stats['dropped_fields'], {'最高分': 1})
        self.assertEqual(self.count('real_admissions'), 2)
        dropped = self.query("SELECT * FROM real_admissions WHERE group_name = '异常最高分'")[0]
        self.assertIsNone(dropped['max_score'])
        self.assertIn('已置空', dropped['note'])
        empty = self.query("SELECT * FROM real_admissions WHERE group_name = '空分数'")[0]
        self.assertIsNone(empty['min_score'])
        self.assertIsNone(empty['min_rank'])
        # 行数对账
        self.assertEqual(stats['parsed'],
                         stats['inserted'] + stats['skipped_existing'] + stats['skipped_duplicate']
                         + stats['invalid'])

    def test_dry_run_does_not_create_or_write_db(self):
        csv_path = self.tmp / '河北_历史_投档_试跑.csv'
        write_csv(csv_path, [make_row(生源省份='河北', 招考科类='历史类')])
        _, report = self.run_cli('--csv', str(csv_path), '--dry-run')
        self.assertTrue(report['dry_run'])
        self.assertEqual(report['files'][0]['inserted'], 1)       # 预计写入
        self.assertEqual(report['files'][0]['data_version_id'], None)
        self.assertFalse(self.db_path.exists(), 'dry-run 不应创建/写入数据库文件')

    def test_school_official_aggregates_max_rank_and_list_rows_fields(self):
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        try:
            def add(school, year, rank, major, subject='物理类'):
                session.add(RealAdmission(
                    school_name=school, province='浙江', exam_year=year, subject_type=subject,
                    admission_type='普通类', round_no='首次投档', group_name=major + '组',
                    major_name=major, min_score=650, min_rank=rank,
                    source_url=f'https://example.gov.cn/{year}', published_at=f'{year}-07-20',
                    fetched_at='2026-11-12T10:00:00+08:00', content_sha256='0' * 64,
                    parser_version='major-csv@1.0.0', doc_status='已导入', group_code='001',
                ))

            add('浙江大学', 2025, 400, '历史学')
            add('浙江大学', 2026, 300, '计算机科学与技术')
            add('浙江大学', 2026, 900, '软件工程')
            add('浙江大学', 2026, 1200, '人工智能')
            session.add(RealAdmission(
                school_name='无位次大学', province='浙江', exam_year=2026, subject_type='物理类',
                admission_type='普通类', round_no='首次投档', group_name='组', major_name='专业',
                min_score=None, min_rank=None, source_url='https://example.gov.cn/x',
                fetched_at='2026-11-12T10:00:00+08:00', content_sha256='1' * 64,
                parser_version='major-csv@1.0.0', doc_status='已导入',
            ))
            session.commit()

            official = real_data.school_official(session, '浙江大学', '浙江')
            self.assertEqual(official['exam_year'], 2026)          # 最近年份
            self.assertEqual(official['min_rank'], 1200)           # 该年最大 min_rank（保守口径）
            self.assertEqual(official['major_level'], True)
            self.assertEqual(official['aggregated_rows'], 3)
            self.assertEqual(official['data_label'], '官方投档数据')
            self.assertIsNone(real_data.school_official(session, '无位次大学', '浙江'))
            self.assertIsNone(real_data.school_official(session, '不存在大学', '浙江'))

            rows = real_data.list_rows(session, '浙江', 2026)
            self.assertEqual(rows['total'], 4)
            item = rows['items'][0]
            for field in ('group_code', 'group_name', 'major_name', 'min_score', 'min_rank',
                          'max_score', 'avg_score', 'actual_count', 'plan_count',
                          'national_code', 'admission_type', 'source_url', 'published_at'):
                self.assertIn(field, item)
        finally:
            session.close()
            engine.dispose()

    def test_summary_exposes_parser_versions(self):
        csv_path = self.tmp / '河北_物理_投档_汇总.csv'
        write_csv(csv_path, [make_row(生源省份='河北')])
        self.run_cli('--csv', str(csv_path))
        engine = create_engine('sqlite:///' + self.db_path.as_posix())
        session = sessionmaker(bind=engine)()
        try:
            result = real_data.summary(session)
            province = next(item for item in result['provinces'] if item['province'] == '河北')
            self.assertIn('major-csv@1.0.0', province['parser_versions'])
            self.assertEqual(result['total_rows'], 1)
        finally:
            session.close()
            engine.dispose()


if __name__ == '__main__':
    unittest.main(verbosity=2)
