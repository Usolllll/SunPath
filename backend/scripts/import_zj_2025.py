"""导入浙江省 2025 年普通类第一段平行投档分数线（官方 xls 已经实测下载）。

用途：补齐画像 6 个生源省份之一的真实投档数据，便于 M7 模拟投档与官方核对演示。
数据文件：ops/2026-11-10_sunpath-week/research/downloads/zj_2025_pg1_toudang.xls
运行：..\\..\\Python311\\python.exe scripts/import_zj_2025.py [--dry-run]
"""
import argparse
import hashlib
import sys
from datetime import date, datetime
from pathlib import Path

import xlrd

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal, engine  # noqa: E402
from app.models.entities import Base, DataVersion, RealAdmission  # noqa: E402
from sqlalchemy import select  # noqa: E402

XLS = BACKEND_DIR.parents[1] / 'ops' / '2026-11-10_sunpath-week' / 'research' / 'downloads' / 'zj_2025_pg1_toudang.xls'
XLS = Path(r'C:\Users\Administrator\Documents\deepseek-harness\default-workspace\ops\2026-11-10_sunpath-week\research\downloads\zj_2025_pg1_toudang.xls')
SOURCE_URL = 'https://www.zjzs.net/art/2025/7/21/art_155_11451.html'
PUBLISHED_AT = '2025-07-21'
PARSER = 'xls-import@1.0.0'


def text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def number(value, *, integer=True):
    if value in (None, '', '-'):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return int(round(result)) if integer else result


def load_rows():
    book = xlrd.open_workbook(str(XLS))
    sheet = book.sheet_by_index(0)
    header = [text(cell) for cell in sheet.row_values(0)]
    index = {name: position for position, name in enumerate(header)}
    required = ['学校名称', '专业代号', '专业名称', '计划数', '分数线', '位次']
    missing = [name for name in required if name not in index]
    if missing:
        raise SystemExit(f'表头缺少字段: {missing}，实际表头: {header}')
    rows, rejected = [], []
    for row_index in range(1, sheet.nrows):
        values = sheet.row_values(row_index)
        school = text(values[index['学校名称']])
        major = text(values[index['专业名称']])
        group_code = text(values[index['专业代号']])
        if not school or not major:
            rejected.append((row_index + 1, '学校或专业为空'))
            continue
        record = {
            'school_name': school[:80], 'province': '浙江', 'exam_year': 2025,
            'subject_type': '综合改革', 'admission_type': '普通类',
            'batch': '普通类第一段', 'round_no': '首次投档',
            'group_code': group_code[:30], 'group_name': major[:120], 'major_name': major[:120],
            'min_score': number(values[index['分数线']]), 'min_rank': number(values[index['位次']]),
            'plan_count': number(values[index['计划数']]),
            'required_subjects': None, 'source_url': SOURCE_URL, 'published_at': PUBLISHED_AT,
            'national_code': None, 'note': '浙江省教育考试院 2025 年普通类第一段平行投档分数线表（xls 原始文件解析）',
        }
        if record['min_score'] is not None and not 0 <= record['min_score'] <= 750:
            rejected.append((row_index + 1, f"分数越界 {record['min_score']}"))
            continue
        if record['min_rank'] is not None and record['min_rank'] <= 0:
            rejected.append((row_index + 1, f"位次非法 {record['min_rank']}"))
            continue
        rows.append(record)
    return rows, rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not XLS.exists():
        raise SystemExit(f'找不到数据文件: {XLS}')

    content_sha = hashlib.sha256(XLS.read_bytes()).hexdigest()
    fetched_at = datetime.now().astimezone().isoformat(timespec='seconds')
    rows, rejected = load_rows()
    print(f'解析 {len(rows) + len(rejected)} 行，有效 {len(rows)}，被拒 {len(rejected)}')
    if rejected:
        print('被拒样例:', rejected[:5])
    if args.dry_run:
        print('样例:', rows[:2])
        return 0

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        existing = db.scalar(select(DataVersion).where(
            DataVersion.province == '浙江', DataVersion.content_sha256 == content_sha,
            DataVersion.is_current.is_(True)))
        if existing:
            print(f'已导入（sha256={content_sha[:12]}…），跳过')
            return 0
        for version in db.scalars(select(DataVersion).where(DataVersion.province == '浙江')).all():
            version.is_current = False
        seen, inserted = set(), 0
        for record in rows:
            key = (record['province'], record['exam_year'], record['subject_type'], record['batch'],
                   record['round_no'], record['group_code'], record['group_name'], record['major_name'],
                   record['school_name'], record['admission_type'])
            if key in seen:
                continue
            seen.add(key)
            db.add(RealAdmission(**record, fetched_at=fetched_at, content_sha256=content_sha,
                                 parser_version=PARSER, doc_status='已导入'))
            inserted += 1
        db.add(DataVersion(dataset='投档线', province='浙江', exam_year=2025, source_url=SOURCE_URL,
                           attachment_url=str(XLS.name), published_at=PUBLISHED_AT, fetched_at=fetched_at,
                           content_sha256=content_sha, parser_version=PARSER, doc_status='已校验',
                           is_current=True, row_count=inserted,
                           note='浙江 2025 普通类第一段平行投档分数线（xls 官方附件）'))
        db.commit()
        print(f'入库 {inserted} 行；dataversion 已登记（sha256={content_sha[:12]}…）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

