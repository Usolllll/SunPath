"""真实投档数据查询与"官方核对"的单元测试（独立内存 SQLite）。"""
import unittest

try:
    import test_workflow  # noqa: F401  先设置临时 DATABASE_URL，避免污染开发库
except ImportError:
    from tests import test_workflow  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import DataVersion, RealAdmission
from app.services import real_data


def build():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    rows = [
        ('浙江大学', '浙江', 2025, 690, 300),
        ('浙江大学', '浙江', 2026, 692, 280),
        ('东北大学', '辽宁', 2025, 630, 18000),
        ('东北大学', '辽宁', 2026, 635, 17500),
        ('南京大学', '黑龙江', 2026, 655, 9000),
    ]
    for index, (school, province, year, score, rank) in enumerate(rows):
        session.add(RealAdmission(
            school_name=school, province=province, exam_year=year, subject_type='物理类',
            batch='本科批', round_no='首次投档', major_name='计算机科学与技术',
            min_score=score, min_rank=rank, source_url=f'https://example.gov.cn/{index}',
            published_at=f'{year}-07-20', fetched_at='2026-11-10T10:00:00+08:00',
            content_sha256='0' * 64, parser_version='csv-import@1.0.0', doc_status='已导入',
        ))
    session.add(DataVersion(dataset='投档线', province='辽宁', exam_year=None, source_url='https://example.gov.cn/ln',
                            published_at='2026-07-20', fetched_at='2026-11-10T10:00:00+08:00',
                            content_sha256='a' * 64, parser_version='csv-import@1.0.0', doc_status='已校验',
                            is_current=True, row_count=2))
    session.commit()
    return session


class RealDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = build()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_summary_groups_provinces_and_versions(self):
        result = real_data.summary(self.db)
        self.assertEqual(result['total_rows'], 5)
        provinces = {item['province']: item for item in result['provinces']}
        self.assertEqual(provinces['辽宁']['rows'], 2)
        self.assertEqual(provinces['辽宁']['years'], [2025, 2026])
        self.assertEqual(provinces['辽宁']['versions'][0]['row_count'], 2)
        self.assertIn('不等于录取线', result['disclaimer'])

    def test_list_rows_filters_by_province_year_and_query(self):
        rows = real_data.list_rows(self.db, '辽宁', 2026)
        self.assertEqual(rows['total'], 1)
        self.assertEqual(rows['items'][0]['school_name'], '东北大学')
        filtered = real_data.list_rows(self.db, '辽宁', None, '东北')
        self.assertEqual(filtered['total'], 2)
        self.assertTrue(all('source_url' in item for item in filtered['items']))

    def test_school_official_returns_latest_year(self):
        official = real_data.school_official(self.db, '浙江大学', '浙江')
        self.assertEqual(official['exam_year'], 2026)
        self.assertEqual(official['min_rank'], 280)
        self.assertEqual(official['data_label'], '官方投档数据')
        self.assertIsNone(real_data.school_official(self.db, '浙江大学', '辽宁'))

    def test_attach_official_sets_none_when_missing(self):
        items = [
            {'id': 1, 'university': {'name': '东北大学'}},
            {'id': 2, 'university': {'name': '不存在的大学'}},
        ]
        real_data.attach_official(self.db, items, '辽宁')
        self.assertEqual(items[0]['official']['min_rank'], 17500)
        self.assertIsNone(items[1]['official'])


if __name__ == '__main__':
    unittest.main()
