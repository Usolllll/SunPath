# -*- coding: utf-8 -*-
"""tests/test_import.py — 真实投档数据导入器（scripts/import_real.py）的隔离测试。

原则：
- 绝不连接 backend/sunpath.db：所有导入都通过 --database-url 指向 tempdir 下的临时 SQLite；
- 通过 subprocess 跑真实 CLI（同时覆盖命令行参数、--database-url 覆盖与 JSON 报告）；
- 构造带 BOM 的小 CSV，覆盖字段映射、非法行被拒、同文件重复键去重、幂等重复导入、
  DataVersion 只保留一个 is_current、以及「哈希变化 → 删旧写新」的版本切换；
- 跑完删除临时目录。

运行（backend 目录下）：
    ..\\..\\Python311\\python.exe -m unittest tests.test_import -v
"""

import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = BACKEND_DIR / 'scripts' / 'import_real.py'
PROVINCE = '测试省'

# 表头尽量贴近真实数据（20 列），并混入「全国院校代码」与两种日期格式的来源链接
CSV_HEADER = [
    '学校名称', '全国院校代码', '生源省份', '招生年份', '招考科类', '招生类型', '投档轮次',
    '专业组代号', '专业组名称', '具体专业', '最低分', '最低位次', '最高分', '平均分',
    '实际录取人数', '计划数', '来源链接', '备注', '选考科目要求', '再选科目要求',
]


def _row(**overrides):
    base = {
        '学校名称': '测试大学', '全国院校代码': '', '生源省份': PROVINCE, '招生年份': '2025',
        '招考科类': '物理类', '招生类型': '普通类', '投档轮次': '首次投档',
        '专业组代号': '001', '专业组名称': '测试大学物理类第001组', '具体专业': '计算机科学与技术',
        '最低分': '680', '最低位次': '120', '最高分': '', '平均分': '',
        '实际录取人数': '', '计划数': '2',
        '来源链接': 'https://www.example.edu.cn/202407/t20240723_123456.html',
        '备注': '测试备注', '选考科目要求': '物理,化学(2门科目考生均须选考方可报考)',
        '再选科目要求': '化学',
    }
    base.update(overrides)
    return [base[column] for column in CSV_HEADER]


def _csv_text(rows):
    lines = [','.join(CSV_HEADER)]
    for row in rows:
        cells = []
        for value in row:
            if any(ch in value for ch in ',"\n'):
                cells.append('"' + value.replace('"', '""') + '"')
            else:
                cells.append(value)
        lines.append(','.join(cells))
    return '\n'.join(lines) + '\n'


def _write_csv(path: Path, rows) -> None:
    path.write_text(_csv_text(rows), encoding='utf-8-sig')  # 真实数据带 UTF-8 BOM


# 11 行：3 行有效、1 行同文件重复键、7 行非法
def _initial_rows():
    return [
        _row(学校名称='A442测试大学', 全国院校代码='10284',
             来源链接='https://www.example.edu.cn/202407/t20240723_123456.html'),
        _row(学校名称='测试师范大学', 全国院校代码='', 招生年份='2025', 招考科类='历史类',
             专业组代号='002', 专业组名称='测试师范大学历史类第002组', 具体专业='汉语言文学',
             最低分='', 最低位次='',
             来源链接='https://www.example.edu.cn/newsinfo/IMS_20250720_42967_xuHWw7pSO3.htm',
             选考科目要求='不提科目要求', 再选科目要求='不限'),
        _row(学校名称='超分大学', 最低分='751'),                    # 分数越界
        _row(学校名称='乱序大学', 最低位次='abc'),                  # 位次非整数
        _row(学校名称=''),                                          # 学校名为空
        _row(学校名称='古早大学', 招生年份='1999'),                 # 年份越界
        _row(学校名称='A442测试大学', 全国院校代码='10284',          # 与第 1 行同键 → 去重
             最低分='681', 最低位次='118'),
        _row(学校名称='外省大学', 生源省份='其他省'),                # 省份不一致
        _row(学校名称='负分大学', 最低分='-5'),                     # 分数越界
        _row(学校名称='坏计划大学', 计划数='abc'),                   # 计划数非整数
        _row(学校名称='第二大学', 全国院校代码='1850', 招生年份='2026',
             专业组代号='003', 专业组名称='第二大学物理类第003组', 具体专业='人工智能',
             最低分='660', 最低位次='500', 来源链接='',
             选考科目要求='', 再选科目要求=''),                     # 4 位省内代号 + 空链接
    ]


# 版本 2：第 1 行分数改动（内容哈希变化）并新增 1 行有效数据
def _revised_rows():
    rows = _initial_rows()
    rows[0] = _row(学校名称='A442测试大学', 全国院校代码='10284', 最低分='682',
                   来源链接='https://www.example.edu.cn/202407/t20240723_123456.html')
    rows.append(_row(学校名称='第三大学', 专业组代号='004', 专业组名称='第三大学物理类第004组',
                     具体专业='软件工程', 最低分='650', 最低位次='800'))
    return rows


class HelperTests(unittest.TestCase):
    """导入器的纯函数（不需要数据库）。"""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('import_real', SCRIPT_PATH)
        cls.importer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.importer)

    def test_header_alias_mapping(self):
        mapping = self.importer.map_headers(
            ['学校名称(院校)', '院校代号及名称', '全国院校代码', '生源省份', '招生年份',
             '招考科类', '招生类型', '投档轮次', '专业组代号', '专业组名称', '具体专业',
             '最低分', '最低位次', '来源链接', '备注', '选考科目要求', '再选科目要求',
             '计划数', '投档人数', '院校代码', '专业代码']
        )
        self.assertEqual(mapping['school_name'], '学校名称(院校)')
        # 同一规范字段已被第一个别名占用，不再覆盖
        self.assertNotIn('院校代号及名称', mapping.values())
        self.assertEqual(mapping['province'], '生源省份')
        self.assertEqual(mapping['subject_type'], '招考科类')
        self.assertEqual(mapping['major_name'], '具体专业')
        self.assertEqual(mapping['plan_count'], '计划数')

    def test_strip_province_school_code(self):
        strip = self.importer.strip_school_code
        self.assertEqual(strip('A442清华大学'), '清华大学')
        self.assertEqual(strip('B1234 北京大学'), '北京大学')
        self.assertEqual(strip('清华大学'), '清华大学')
        self.assertEqual(strip('  A123浙江大学 '), '浙江大学')

    def test_parse_published_at(self):
        parse = self.importer.parse_published_at
        self.assertEqual(parse('http://zsksy.guizhou.gov.cn/ygpt/tdqk/202407/t20240723_85148150.html'),
                         '2024-07-23')
        self.assertEqual(parse('https://www.lnzsks.com/newsinfo/IMS_20230720_42967_xuHWw7pSO3.htm'),
                         '2023-07-20')
        self.assertIsNone(parse('https://www.lzk.hl.cn/gkpd/gkxx/202407/t99999999_1.htm'))
        self.assertIsNone(parse(''))

    def test_infer_year_from_filename(self):
        infer = self.importer.infer_year_from_filename
        self.assertEqual(infer(Path('辽宁_2023-2026_投档最低分.csv')), 2023)
        self.assertEqual(infer(Path('黑龙江_2024-2026_投档最低分.csv')), 2024)
        self.assertIsNone(infer(Path('未知文件.csv')))


class ImportCliTests(unittest.TestCase):
    """端到端：subprocess 跑 CLI + 临时 SQLite。"""

    @classmethod
    def setUpClass(cls):
        cls.tempdir = Path(tempfile.mkdtemp(prefix='sunpath-import-test-'))
        cls.csv_path = cls.tempdir / '测试_2025-2026_投档最低分.csv'
        cls.db_path = cls.tempdir / 'test_import.db'
        cls.database_url = 'sqlite:///' + cls.db_path.as_posix()
        _write_csv(cls.csv_path, _initial_rows())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tempdir, ignore_errors=True)

    # ---------------------------------------------------------------- 工具
    def _run(self, report_name: str) -> tuple[subprocess.CompletedProcess, dict]:
        report_path = self.tempdir / report_name
        env = dict(os.environ)
        env.pop('DATABASE_URL', None)
        env['PYTHONPATH'] = str(BACKEND_DIR)
        env['PYTHONIOENCODING'] = 'utf-8'
        env['TMP'] = str(self.tempdir)
        env['TEMP'] = str(self.tempdir)
        process = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), '--csv', str(self.csv_path),
             '--province', PROVINCE, '--database-url', self.database_url,
             '--json-report', str(report_path)],
            cwd=str(BACKEND_DIR), env=env, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=180,
        )
        self.assertEqual(process.returncode, 0, f'导入器失败：\nSTDOUT:\n{process.stdout}\nSTDERR:\n{process.stderr}')
        self.assertTrue(report_path.is_file(), '没有生成 JSON 报告')
        payload = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual(len(payload['files']), 1)
        return process, payload['files'][0]

    def _query(self, sql: str, params=()):
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(sql, params).fetchall()

    def _count(self, table: str) -> int:
        return self._query(f'SELECT COUNT(*) AS n FROM {table}')[0]['n']

    # ---------------------------------------------------------------- 用例
    def test_zz_full_flow(self):
        """单方法内顺序覆盖：首次导入 → 行数对账/字段映射 → 幂等 → 哈希变化换版本。"""
        csv_bytes = self.csv_path.read_bytes()
        expected_sha = hashlib.sha256(csv_bytes).hexdigest()

        # ---------- 1) 首次导入 ----------
        process, report = self._run('report1.json')
        self.assertEqual(report['rows_read'], 11)
        self.assertEqual(report['accepted'], 3)
        self.assertEqual(report['skipped_duplicate'], 1)
        self.assertEqual(report['rejected'], 7)
        self.assertEqual(report['rows_read'],
                         report['accepted'] + report['skipped_duplicate'] + report['rejected'],
                         '行数对账不成立：读入 ≠ 有效 + 重复跳过 + 被拒')
        self.assertEqual(report['inserted'], 3)
        self.assertEqual(report['content_sha256'], expected_sha)
        self.assertIn('导入报告', process.stdout)
        self.assertIn('对账：11 = 3 + 1 + 7（一致）', process.stdout)

        # 被拒原因分布
        self.assertEqual(report['reject_reasons'], {
            '最低分越界(0-750)': 2,
            '最低位次非整数': 1,
            '学校名为空': 1,
            '招生年份越界(2020-2030)': 1,
            '省份与参数不一致': 1,
            '计划数非整数': 1,
        })

        # 字段映射（第 1 行）
        self.assertEqual(self._count('real_admissions'), 3)
        row = self._query(
            "SELECT * FROM real_admissions WHERE school_name = '测试大学'"
        )[0]
        self.assertEqual(row['national_code'], '10284')     # 5 位国标码保留
        self.assertEqual(row['province'], PROVINCE)
        self.assertEqual(row['exam_year'], 2025)
        self.assertEqual(row['subject_type'], '物理类')
        self.assertEqual(row['admission_type'], '普通类')
        self.assertIsNone(row['batch'])                      # 数据无「批次」列 → 留空
        self.assertEqual(row['round_no'], '首次投档')
        self.assertEqual(row['group_code'], '001')
        self.assertEqual(row['group_name'], '测试大学物理类第001组')
        self.assertEqual(row['major_name'], '计算机科学与技术')
        self.assertEqual(row['min_score'], 680)
        self.assertEqual(row['min_rank'], 120)
        self.assertIsNone(row['max_score'])
        self.assertIsNone(row['avg_score'])
        self.assertIsNone(row['actual_count'])
        self.assertEqual(row['plan_count'], 2)
        self.assertIn('化学', row['required_subjects'])
        self.assertEqual(row['published_at'], '2024-07-23')
        self.assertRegex(row['fetched_at'], r'\+08:00$')
        self.assertEqual(row['content_sha256'], expected_sha)
        self.assertEqual(row['parser_version'], 'csv-import@1.0.0')
        self.assertEqual(row['doc_status'], '已导入')

        # 缺分/缺位次行允许入库，字段为空
        row2 = self._query(
            "SELECT * FROM real_admissions WHERE school_name = '测试师范大学'"
        )[0]
        self.assertIsNone(row2['min_score'])
        self.assertIsNone(row2['min_rank'])
        self.assertEqual(row2['published_at'], '2025-07-20')
        self.assertEqual(row2['required_subjects'], '不提科目要求')

        # 4 位省内代号不得写入 national_code；空链接回落 local:// 且 published_at 为空
        row3 = self._query("SELECT * FROM real_admissions WHERE school_name = '第二大学'")[0]
        self.assertIsNone(row3['national_code'])
        self.assertTrue(row3['source_url'].startswith('local://'))
        self.assertIsNone(row3['published_at'])
        self.assertEqual(row3['exam_year'], 2026)

        # DataVersion：每省 1 条 is_current
        versions = self._query('SELECT * FROM data_versions')
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]['dataset'], '投档线')
        self.assertEqual(versions[0]['province'], PROVINCE)
        self.assertEqual(versions[0]['is_current'], 1)
        self.assertEqual(versions[0]['row_count'], 3)
        self.assertEqual(versions[0]['content_sha256'], expected_sha)
        self.assertEqual(versions[0]['parser_version'], 'csv-import@1.0.0')

        # ---------- 2) 幂等：同文件重复导入不新增 ----------
        process2, report2 = self._run('report2.json')
        self.assertTrue(report2['skipped_existing'])
        self.assertEqual(report2['inserted'], 0)
        self.assertIn('已导入，跳过', process2.stdout)
        self.assertEqual(self._count('real_admissions'), 3)
        self.assertEqual(self._count('data_versions'), 1)
        self.assertEqual(
            self._query('SELECT COUNT(*) AS n FROM data_versions WHERE is_current = 1')[0]['n'], 1
        )

        # ---------- 3) 哈希变化 → 删旧写新，只保留一个 is_current ----------
        _write_csv(self.csv_path, _revised_rows())
        new_sha = hashlib.sha256(self.csv_path.read_bytes()).hexdigest()
        self.assertNotEqual(new_sha, expected_sha)
        _, report3 = self._run('report3.json')
        self.assertEqual(report3['rows_read'], 12)
        self.assertEqual(report3['accepted'], 4)
        self.assertEqual(report3['skipped_duplicate'], 1)
        self.assertEqual(report3['rejected'], 7)
        self.assertEqual(report3['inserted'], 4)
        self.assertEqual(report3['deleted_rows'], 3, '应删除该省由本导入器写入的旧行')
        self.assertEqual(report3['retired_versions'], 1, '旧 DataVersion 应被置为非当前')

        self.assertEqual(self._count('real_admissions'), 4)
        scores = [r['min_score'] for r in self._query(
            'SELECT min_score FROM real_admissions ORDER BY min_score DESC')]
        self.assertEqual(scores, [682, 660, 650, None])
        self.assertEqual(self._count('data_versions'), 2)
        currents = self._query('SELECT * FROM data_versions WHERE is_current = 1')
        self.assertEqual(len(currents), 1)
        self.assertEqual(currents[0]['content_sha256'], new_sha)
        self.assertEqual(currents[0]['row_count'], 4)
        old = self._query('SELECT * FROM data_versions ORDER BY id')[0]
        self.assertEqual(old['is_current'], 0)
        self.assertEqual(old['content_sha256'], expected_sha)

        # 所有行的内容哈希都已切到新版本（旧数据无残留）
        hashes = {r['content_sha256'] for r in self._query('SELECT content_sha256 FROM real_admissions')}
        self.assertEqual(hashes, {new_sha})

        # ---------- 4) 修订版再跑一次：仍然幂等 ----------
        process4, report4 = self._run('report4.json')
        self.assertTrue(report4['skipped_existing'])
        self.assertEqual(self._count('real_admissions'), 4)
        self.assertEqual(self._count('data_versions'), 2)
        self.assertIn('已导入，跳过', process4.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
