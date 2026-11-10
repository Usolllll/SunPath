#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SunPath 二期 D2：官方真实投档数据导入器（CSV → real_admissions / data_versions）。

用法（在 backend 目录下执行，必须用 Python 3.11）：

    # 单文件（--csv 可给绝对路径；--province 必填）
    python scripts/import_real.py --csv <path.csv> --province 辽宁 [--limit N] [--dry-run]

    # 三份固定文件一次导入（按工作区相对文件名查找）
    python scripts/import_real.py --all [--limit N] [--dry-run]

    # 覆盖数据库连接（测试/演练用；不写 backend/sunpath.db）
    python scripts/import_real.py --csv <path.csv> --province 测试 --database-url sqlite:///C:/tmp/x.db

设计要点：
- 仅用标准库 csv + hashlib 流式读取，大文件不整体进内存；
- 表头自适应映射（学校名称 / 学校名称(院校) / 院校代号及名称 等别名都能识别）；
- 行级校验：校名、分数 0–750、位次正整数、年份 2020–2030、省份一致；
- 同一文件内按 (province, exam_year, subject_type, batch, round_no, group_code,
  group_name, major_name, school_name, admission_type) 去重（与 ORM 唯一键一致）；
- 幂等：以 (province, content_sha256) 判断。已有相同哈希且 is_current 的 DataVersion
  则整份文件跳过；否则删除该省由本导入器写入的旧 RealAdmission、旧 DataVersion
  is_current 置 False，再写新版本；
- 整份文件一个事务，失败回滚；
- 导入结束打印行数对账、被拒原因分布、空值率、抽样与 DataVersion id；
- 可选 --json-report 落一份机器可读报告（测试用）。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

PARSER_VERSION = 'csv-import@1.0.0'
DATASET = '投档线'
DOC_STATUS = '已导入'
CST = timezone(timedelta(hours=8))
INSERT_CHUNK = 2000
MAX_SCHOOL_LEN = 80
MAX_TEXT_LEN = 120          # group_name / major_name / required_subjects 的 ORM 长度
MAX_NOTE_LEN = 500
MAX_URL_LEN = 500
MIN_YEAR, MAX_YEAR = 2020, 2030
MIN_SCORE, MAX_SCORE = 0, 750

# --all 使用的固定文件（数据放在工作区根目录，只读）
DEFAULT_FILES = (
    ('辽宁', '辽宁_2023-2026_投档最低分.csv'),
    ('贵州', '贵州_2024-2026_投档最低分.csv'),
    ('黑龙江', '黑龙江_2024-2026_投档最低分.csv'),
)

# 表头别名 → 规范字段名。按顺序取第一个命中的列。
HEADER_ALIASES = {
    'school_name': ('学校名称', '学校名称(院校)', '院校代号及名称', '院校名称', '招生院校', '院校'),
    'national_code': ('全国院校代码', '院校国标代码', '国标代码', '全国院校标代码'),
    'province': ('生源省份', '省份', '生源省'),
    'exam_year': ('招生年份', '年份', '录取年份', '招生年度'),
    'subject_type': ('招考科类', '科类', '招生科类', '选考科类', '文理科'),
    'admission_type': ('招生类型', '计划性质', '招生性质'),
    'batch': ('批次', '录取批次', '招生批次'),
    'round_no': ('投档轮次', '轮次', '投档批次'),
    'group_code': ('专业组代号', '院校专业组代号', '专业组代码', '专业组号'),
    'group_name': ('专业组名称', '院校专业组名称', '专业组'),
    'major_name': ('具体专业', '专业名称', '专业'),
    'min_score': ('最低分', '投档最低分', '最低投档分', '最低投档线'),
    'min_rank': ('最低位次', '投档最低位次', '最低排名', '最低位次排名'),
    'max_score': ('最高分', '最高投档分'),
    'avg_score': ('平均分', '平均投档分'),
    'actual_count': ('实际录取人数', '录取人数'),
    'plan_count': ('计划数', '招生计划数', '计划人数'),
    'source_url': ('来源链接', '来源网址', '来源', '原文链接'),
    'note': ('备注', '说明'),
    'required_subjects': ('选考科目要求', '选科要求', '选考要求'),
    'reselected_subjects': ('再选科目要求', '再选科目'),
    'major_code': ('专业代码',),
    'school_province_code': ('院校代码', '院校代号', '省内院校代码'),
}

_ALIAS_INDEX = {
    _alias: _canonical
    for _canonical, _aliases in HEADER_ALIASES.items()
    for _alias in _aliases
}
_WS_RE = re.compile(r'[\s\u00a0\u3000]+')
_SCHOOL_CODE_RE = re.compile(r'^[A-Za-zＡ-Ｚａ-ｚ]{1,2}\d{2,5}[\s\-_/、,，:：.]*')
_INT_RE = re.compile(r'^[+-]?\d+$')
_NATIONAL_CODE_RE = re.compile(r'^\d{5}$')
_DATE_TOKEN_RE = re.compile(r'(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)')
_FILENAME_YEAR_RE = re.compile(r'(20\d{2})')

SUBJECT_TYPE_MAP = {
    '历史学科类': '历史类',
    '物理学科类': '物理类',
    '历史类': '历史类',
    '物理类': '物理类',
}

_SESSION_CACHE: dict[str, tuple] = {}


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def clean_text(value) -> str:
    """去 BOM、统一各类空白为单空格并 strip。None/空 → ''。"""
    if value is None:
        return ''
    text = str(value).replace('\ufeff', '')
    return _WS_RE.sub(' ', text).strip()


def _norm_header(value) -> str:
    return re.sub(r'\s+', '', clean_text(value).replace('（', '(').replace('）', ')')).lower()


def map_headers(fieldnames) -> dict:
    """表头 → {规范字段名: 实际列名}。同一规范字段只取第一个命中的列。"""
    mapping: dict[str, str] = {}
    for header in fieldnames or []:
        canonical = _ALIAS_INDEX.get(_norm_header(header))
        if canonical and canonical not in mapping:
            mapping[canonical] = header
    return mapping


def _pick(row, mapping, canonical) -> str:
    header = mapping.get(canonical)
    return row.get(header) if header else None


def strip_school_code(name: str) -> str:
    """去掉校名前的省内代号前缀，如 'A442清华大学' → '清华大学'。"""
    name = (name or '').strip()
    previous = None
    while previous != name:
        previous = name
        name = _SCHOOL_CODE_RE.sub('', name)
    return name.strip()


def parse_int(value) -> tuple[int | None, str | None]:
    """返回 (int 或 None, 错误码或 None)。空值返回 (None, None)。"""
    text = clean_text(value)
    if not text:
        return None, None
    if not _INT_RE.match(text):
        return None, '非整数'
    return int(text), None


def parse_published_at(source_url) -> str | None:
    """从来源链接里解析官方发布日期（兼容 /202407/t20240723_ 与 IMS_20230720_）。"""
    url = clean_text(source_url)
    if not url:
        return None
    for match in _DATE_TOKEN_RE.finditer(url):
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if 2000 <= year <= MAX_YEAR and 1 <= month <= 12 and 1 <= day <= 31:
            return f'{year:04d}-{month:02d}-{day:02d}'
    return None


def normalize_subject_type(value) -> str:
    text = clean_text(value)
    return SUBJECT_TYPE_MAP.get(text, text)


def truncate_text(value: str, limit: int) -> tuple[str | None, bool]:
    """按 ORM 长度截断；返回 (截断后的值, 是否发生截断)。空 → (None, False)。"""
    text = clean_text(value)
    if not text:
        return None, False
    if len(text) <= limit:
        return text, False
    return text[: limit - 1] + '…', True


def infer_year_from_filename(path: Path) -> int | None:
    years = [int(y) for y in _FILENAME_YEAR_RE.findall(path.name)]
    years = [y for y in years if MIN_YEAR <= y <= MAX_YEAR]
    return min(years) if years else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _local_source_url(path: Path) -> str:
    return 'local://' + path.name


# --------------------------------------------------------------------------- #
# 路径解析
# --------------------------------------------------------------------------- #
def candidate_data_dirs(data_dir: str | None = None) -> list[Path]:
    dirs: list[Path] = []
    if data_dir:
        dirs.append(Path(data_dir).expanduser().resolve())
    script = Path(__file__).resolve()
    cwd = Path.cwd()
    dirs.extend([cwd, *list(cwd.parents)[:3]])
    dirs.extend(script.parents[level] for level in range(0, min(7, len(script.parents))))
    seen, unique = set(), []
    for directory in dirs:
        key = str(directory).lower()
        if key not in seen:
            seen.add(key)
            unique.append(directory)
    return unique


def resolve_data_file(filename: str, data_dir: str | None = None) -> Path:
    for directory in candidate_data_dirs(data_dir):
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f'找不到数据文件 {filename}；已尝试目录：\n  '
        + '\n  '.join(str(d) for d in candidate_data_dirs(data_dir))
        + '\n请用 --csv 指定绝对路径，或用 --data-dir 指定所在目录。'
    )


# --------------------------------------------------------------------------- #
# 数据库连接（惰性导入，便于单元测试不依赖 SQLAlchemy）
# --------------------------------------------------------------------------- #
def _looks_like_absolute_sqlite(url: str) -> bool:
    if not url.startswith('sqlite:///'):
        return False
    path = url[len('sqlite:///'):]
    if path.startswith('/'):
        return True
    return len(path) > 2 and path[1] == ':'


def _make_override_engine(database_url: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    from app.models.entities import DataVersion, RealAdmission  # noqa: F401  确保 ORM 已注册

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={'check_same_thread': False} if database_url.startswith('sqlite') else {},
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False), engine


def get_session_factory(database_url: str | None = None):
    """返回 (session_factory, RealAdmission, DataVersion)。

    - 显式 --database-url，或环境变量 DATABASE_URL 是绝对 SQLite 路径时：自建 engine
      直接使用该 URL（避免 app.core.database 把绝对路径当相对文件名重写）；
    - 否则使用 app.core.database.SessionLocal（backend/.env 的 DATABASE_URL）。
    """
    override = database_url
    if not override:
        env_url = os.environ.get('DATABASE_URL', '')
        if env_url and _looks_like_absolute_sqlite(env_url):
            override = env_url
    key = override or '__default__'
    if key in _SESSION_CACHE:
        return _SESSION_CACHE[key]

    if override:
        session_factory, engine = _make_override_engine(override)
        from app.models.entities import DataVersion, RealAdmission
    else:
        from app.core.database import SessionLocal, engine
        from app.models.entities import DataVersion, RealAdmission

        from app.core.database import Base
        Base.metadata.create_all(engine)
        session_factory = SessionLocal
    result = (session_factory, RealAdmission, DataVersion)
    _SESSION_CACHE[key] = result
    return result


# --------------------------------------------------------------------------- #
# 行解析 / 校验
# --------------------------------------------------------------------------- #
def build_record(row, mapping, province: str, path: Path, default_year: int | None,
                 fetched_at: str, content_sha256: str) -> tuple[dict | None, str | None, dict]:
    """把一行 CSV 转成 RealAdmission 字段 dict。

    返回 (record, reject_reason, info)；reject_reason 非空表示该行被拒。
    info 里带 original_major / original_group / truncated 等辅助信息。
    """
    info = {'truncated': [], 'original_major': None, 'original_group': None}
    if None in row:  # DictReader 遇到多余列会塞进 None 键
        return None, '列数不符(多列)', info
    if any(value is None for value in row.values()):
        return None, '列数不符(缺列)', info

    school = strip_school_code(clean_text(_pick(row, mapping, 'school_name')))
    if not school:
        return None, '学校名为空', info
    if len(school) > MAX_SCHOOL_LEN:
        return None, f'学校名超长(>{MAX_SCHOOL_LEN})', info

    row_province = clean_text(_pick(row, mapping, 'province'))
    if row_province and row_province != province:
        return None, '省份与参数不一致', info

    year, year_error = parse_int(_pick(row, mapping, 'exam_year'))
    if year_error:
        return None, '招生年份非整数', info
    if year is None:
        year = default_year
    if year is None:
        return None, '招生年份缺失', info
    if not (MIN_YEAR <= year <= MAX_YEAR):
        return None, f'招生年份越界({MIN_YEAR}-{MAX_YEAR})', info

    subject_type = normalize_subject_type(_pick(row, mapping, 'subject_type'))
    if not subject_type:
        return None, '招考科类为空', info

    scores = {}
    for canonical, label in (('min_score', '最低分'), ('max_score', '最高分'), ('avg_score', '平均分')):
        value, error = parse_int(_pick(row, mapping, canonical))
        if error:
            return None, f'{label}非整数', info
        if value is not None and not (MIN_SCORE <= value <= MAX_SCORE):
            return None, f'{label}越界({MIN_SCORE}-{MAX_SCORE})', info
        scores[canonical] = value

    min_rank, rank_error = parse_int(_pick(row, mapping, 'min_rank'))
    if rank_error:
        return None, '最低位次非整数', info
    if min_rank is not None and min_rank <= 0:
        return None, '最低位次非正整数', info

    counts = {}
    for canonical, label in (('plan_count', '计划数'), ('actual_count', '实际录取人数')):
        value, error = parse_int(_pick(row, mapping, canonical))
        if error:
            return None, f'{label}非整数', info
        if value is not None and value < 0:
            return None, f'{label}为负数', info
        counts[canonical] = value

    national_code = clean_text(_pick(row, mapping, 'national_code'))
    if national_code and not _NATIONAL_CODE_RE.match(national_code):
        national_code = ''  # 非 5 位国标码（如省内 4 位代号）一律留空，不冒充国标

    group_code, _ = truncate_text(_pick(row, mapping, 'group_code'), 30)
    group_name, group_truncated = truncate_text(_pick(row, mapping, 'group_name'), MAX_TEXT_LEN)
    major_name, major_truncated = truncate_text(_pick(row, mapping, 'major_name'), MAX_TEXT_LEN)
    if group_truncated:
        info['truncated'].append('group_name')
        info['original_group'] = clean_text(_pick(row, mapping, 'group_name'))
    if major_truncated:
        info['truncated'].append('major_name')
        info['original_major'] = clean_text(_pick(row, mapping, 'major_name'))

    required = clean_text(_pick(row, mapping, 'required_subjects'))
    reselected = clean_text(_pick(row, mapping, 'reselected_subjects'))
    no_limit = ('不提科目要求', '不限')
    if reselected and not required:
        required = f'再选：{reselected}'
    elif reselected and reselected not in required and reselected not in no_limit and required not in no_limit:
        # 选考要求里没提到再选科目时才补充，避免「不提科目要求；再选：不限」这类冗余
        required = f'{required}；再选：{reselected}'
    required, _ = truncate_text(required, MAX_TEXT_LEN)

    source_url = clean_text(_pick(row, mapping, 'source_url'))
    if not source_url:
        source_url = _local_source_url(path)
    if len(source_url) > MAX_URL_LEN:
        source_url = source_url[:MAX_URL_LEN]

    admission_type, _ = truncate_text(_pick(row, mapping, 'admission_type'), 20)
    batch, _ = truncate_text(_pick(row, mapping, 'batch'), 30)
    round_no, _ = truncate_text(_pick(row, mapping, 'round_no'), 20)

    note_parts: list[str] = []
    if info['original_major']:
        note_parts.append(f'专业名原文：{info["original_major"]}')
    if info['original_group'] and info['original_group'] != info['original_major']:
        note_parts.append(f'专业组名原文：{info["original_group"]}')
    raw_note = clean_text(_pick(row, mapping, 'note'))
    if raw_note:
        note_parts.append(raw_note)
    note = '；'.join(note_parts) or None
    if note and len(note) > MAX_NOTE_LEN:
        note = note[: MAX_NOTE_LEN - 1] + '…'

    record = {
        'school_name': school,
        'national_code': national_code or None,
        'province': province,
        'exam_year': year,
        'subject_type': subject_type,
        'admission_type': admission_type,
        'batch': batch,
        'round_no': round_no,
        'group_code': group_code,
        'group_name': group_name,
        'major_name': major_name,
        'min_score': scores['min_score'],
        'min_rank': min_rank,
        'max_score': scores['max_score'],
        'avg_score': scores['avg_score'],
        'actual_count': counts['actual_count'],
        'plan_count': counts['plan_count'],
        'required_subjects': required,
        'source_url': source_url,
        'published_at': parse_published_at(source_url),
        'fetched_at': fetched_at,
        'content_sha256': content_sha256,
        'parser_version': PARSER_VERSION,
        'doc_status': DOC_STATUS,
        'note': note,
    }
    return record, None, info


def dedupe_key(record: dict) -> tuple:
    """与 ORM UniqueConstraint 一致的同一文件内去重键。"""
    return (
        record['province'], record['exam_year'], record['subject_type'],
        record['batch'] or '', record['round_no'] or '', record['group_code'] or '',
        record['group_name'] or '', record['major_name'] or '', record['school_name'],
        record['admission_type'] or '',
    )


# --------------------------------------------------------------------------- #
# 报告
# --------------------------------------------------------------------------- #
def _pct(part: int, total: int) -> str:
    return f'{(part / total * 100):.2f}%' if total else '0.00%'


def _sample_lines(record: dict) -> str:
    pieces = [
        record['province'], str(record['exam_year']), record['subject_type'],
        record['school_name'],
    ]
    if record['group_name']:
        pieces.append('组:' + record['group_name'])
    if record['major_name']:
        pieces.append('专业:' + record['major_name'])
    pieces.append(f"最低分:{record['min_score'] if record['min_score'] is not None else '-'}")
    pieces.append(f"位次:{record['min_rank'] if record['min_rank'] is not None else '-'}")
    return ' | '.join(pieces)


def print_report(stats: dict, out=print) -> None:
    out('=' * 78)
    out(f"导入报告：{Path(stats['file']).name}")
    out(f"  省份={stats['province']}  sha256={stats['content_sha256']}")
    out(f"  数据行数={stats['rows_read']}  有效行={stats['accepted']}  入库={stats['inserted']}")
    if stats['skipped_existing']:
        out('  跳过=1（整份文件已导入，未重复解析；行数对账不适用）  被拒=0')
    else:
        out(f"  跳过={stats['skipped']}（重复键 {stats['skipped_duplicate']}，"
            f"幂等跳过 {stats['skipped_existing_rows']}）  被拒={stats['rejected']}")
        if stats['rows_read']:
            out(f"  对账：{stats['rows_read']} = {stats['accepted']} + {stats['skipped']}"
                f" + {stats['rejected']}"
                f"（{'一致' if stats['rows_read'] == stats['accepted'] + stats['skipped'] + stats['rejected'] else '不一致'}）")
    if stats['dry_run']:
        out('  [dry-run] 未写入数据库')
    elif stats['skipped_existing']:
        out(f"  已导入，跳过（命中相同哈希的当前版本 DataVersion id={stats.get('data_version_id')}）")
    if stats.get('deleted_rows'):
        out(f"  清理旧数据：RealAdmission {stats['deleted_rows']} 行，旧 DataVersion 置非当前 "
            f"{stats['retired_versions']} 条")
    if stats['limit']:
        out(f"  [限量解析] 只读取前 {stats['limit']} 行数据")
    if stats['years']:
        out('  年份分布：' + '，'.join(f'{y}:{n}' for y, n in sorted(stats['years'].items())))
    if stats['subject_types']:
        out('  科类分布：' + '，'.join(f'{k}:{n}' for k, n in stats['subject_types'].items()))
    if stats['reject_reasons']:
        out('  被拒原因分布：' + '；'.join(f'{k}:{n}' for k, n in stats['reject_reasons'].most_common()))
    if stats['accepted']:
        out('  空值率（按有效行）：' + '，'.join(
            f"{field} {_pct(count, stats['accepted'])}（{count}/{stats['accepted']}）"
            for field, count in stats['null_counts'].items()
        ))
    else:
        out('  空值率：无有效数据行')
    for line in stats['samples']:
        out(f'  抽样：{line}')
    if stats.get('data_version_id') is not None:
        out(f"  DataVersion id={stats['data_version_id']} is_current={stats['data_version_current']} "
            f"row_count={stats['inserted'] if not stats['skipped_existing'] else '-'}")
    out(f"  耗时 {stats['elapsed_seconds']:.2f}s")
    out('')


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def import_csv(csv_path, province: str, *, limit: int | None = None, dry_run: bool = False,
               database_url: str | None = None, json_report: str | None = None,
               out=print) -> dict:
    """解析并导入一份 CSV；返回统计 dict（测试可直接断言）。"""
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f'CSV 不存在：{path}')
    started = datetime.now(CST)
    content_sha256 = sha256_file(path)
    fetched_at = started.isoformat(timespec='seconds')
    default_year = infer_year_from_filename(path)

    stats: dict = {
        'file': str(path), 'province': province, 'dry_run': dry_run, 'limit': limit,
        'content_sha256': content_sha256, 'parser_version': PARSER_VERSION,
        'rows_read': 0, 'accepted': 0, 'inserted': 0,
        'skipped': 0, 'skipped_existing_rows': 0, 'skipped_duplicate': 0,
        'skipped_existing': False, 'rejected': 0, 'reject_reasons': Counter(),
        'years': Counter(), 'subject_types': Counter(),
        'source_urls': set(), 'first_url': None, 'first_published': None,
        'null_counts': {'min_score': 0, 'min_rank': 0, 'required_subjects': 0,
                        'group_code': 0, 'major_name': 0, 'published_at': 0, 'national_code': 0},
        'samples': [], 'data_version_id': None, 'data_version_current': None,
        'deleted_rows': 0, 'retired_versions': 0,
        'elapsed_seconds': 0.0,
    }
    sample_records: list[dict] = []

    if not dry_run:
        session_factory, RealAdmission, DataVersion = get_session_factory(database_url)
        session = session_factory()
        try:
            existing = (
                session.query(DataVersion)
                .filter(DataVersion.dataset == DATASET,
                        DataVersion.province == province,
                        DataVersion.content_sha256 == content_sha256,
                        DataVersion.is_current.is_(True))
                .first()
            )
            if existing is not None:
                stats['skipped_existing'] = True
                stats['skipped'] = 1
                stats['data_version_id'] = existing.id
                stats['data_version_current'] = bool(existing.is_current)
                stats['elapsed_seconds'] = (datetime.now(CST) - started).total_seconds()
                out(f"[{province}] 已导入，跳过：{path.name}（DataVersion id={existing.id}，"
                    f"sha256={content_sha256[:16]}…）")
                _write_json_report(json_report, stats)
                print_report(stats, out=out)
                return stats

            # 上面的幂等查询已隐式开启事务；先结束它，下面用显式事务块
            session.rollback()
            from sqlalchemy import insert

            with session.begin():
                # 幂等重检查放在事务内，避免并发重复导入
                again = (
                    session.query(DataVersion)
                    .filter(DataVersion.dataset == DATASET,
                            DataVersion.province == province,
                            DataVersion.content_sha256 == content_sha256,
                            DataVersion.is_current.is_(True))
                    .first()
                )
                if again is not None:
                    stats['skipped_existing'] = True
                    stats['skipped'] = 1
                    stats['data_version_id'] = again.id
                    stats['data_version_current'] = bool(again.is_current)
                else:
                    stats['retired_versions'] = (
                        session.query(DataVersion)
                        .filter(DataVersion.dataset == DATASET,
                                DataVersion.province == province,
                                DataVersion.is_current.is_(True))
                        .update({'is_current': False}, synchronize_session=False)
                    )
                    stats['deleted_rows'] = (
                        session.query(RealAdmission)
                        .filter(RealAdmission.province == province,
                                RealAdmission.parser_version.like(f'{PARSER_VERSION.split("@")[0]}@%'))
                        .delete(synchronize_session=False)
                    )
                    _consume_csv(path, province, default_year, fetched_at, content_sha256,
                                 limit, session, insert, RealAdmission, stats, sample_records)

                    first_url = stats['first_url']
                    first_published = stats['first_published']
                    version = DataVersion(
                        dataset=DATASET,
                        province=province,
                        exam_year=None,
                        source_url=(first_url or _local_source_url(path))[:MAX_URL_LEN],
                        attachment_url=None,
                        published_at=first_published,
                        fetched_at=fetched_at,
                        content_sha256=content_sha256,
                        parser_version=PARSER_VERSION,
                        doc_status=DOC_STATUS,
                        is_current=limit is None,
                        row_count=stats['inserted'],
                        note=(
                            f'本地文件：{path.name}；多年度；来源链接 {len(stats["source_urls"])} 个'
                            + ('；限量解析，未作为当前版本' if limit is not None else '')
                        )[:200],
                    )
                    session.add(version)
                    session.flush()
                    stats['data_version_id'] = version.id
                    stats['data_version_current'] = bool(version.is_current)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    else:
        _consume_csv(path, province, default_year, fetched_at, content_sha256,
                     limit, None, None, None, stats, sample_records)

    if not stats['skipped_existing']:
        stats['skipped'] = stats['skipped_duplicate']
    stats['elapsed_seconds'] = (datetime.now(CST) - started).total_seconds()
    _write_json_report(json_report, stats)
    print_report(stats, out=out)
    return stats


def _consume_csv(path: Path, province: str, default_year, fetched_at: str,
                 content_sha256: str, limit: int | None, session, insert_fn,
                 RealAdmission, stats: dict, sample_records: list[dict]) -> None:
    """流式解析 CSV；session/insert_fn 为 None 时只统计（dry-run）。"""
    seen_keys: set[tuple] = set()
    pending: list[dict] = []
    mapping: dict = {}
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f'CSV 没有表头：{path}')
        mapping = map_headers(reader.fieldnames)
        required_headers = ['school_name', 'exam_year', 'subject_type']
        missing = [field for field in required_headers if field not in mapping]
        if missing:
            raise ValueError(
                f'CSV 表头缺少必要列（规范字段 {missing}）；实际表头：{reader.fieldnames}'
            )
        for row in reader:
            if limit is not None and stats['rows_read'] >= limit:
                break
            stats['rows_read'] += 1
            record, reason, _info = build_record(
                row, mapping, province, path, default_year, fetched_at, content_sha256
            )
            if reason:
                stats['rejected'] += 1
                stats['reject_reasons'][reason] += 1
                continue

            key = dedupe_key(record)
            if key in seen_keys:
                stats['skipped_duplicate'] += 1
                continue
            seen_keys.add(key)

            stats['accepted'] += 1
            if session is not None:
                stats['inserted'] += 1
            stats['years'][record['exam_year']] += 1
            stats['subject_types'][record['subject_type']] += 1
            stats['source_urls'].add(record['source_url'])
            if stats['first_url'] is None:
                # DataVersion 的来源链接与发布日期取同一行，避免 URL 与日期跨年错配
                stats['first_url'] = record['source_url']
                stats['first_published'] = record['published_at']
            for field in stats['null_counts']:
                if record.get(field) is None:
                    stats['null_counts'][field] += 1
            if len(sample_records) < 3:
                sample_records.append(record)
            if len(stats['samples']) < 3:
                stats['samples'].append(_sample_lines(record))

            if session is not None:
                pending.append(record)
                if len(pending) >= INSERT_CHUNK:
                    session.execute(insert_fn(RealAdmission), pending)
                    pending = []
    if session is not None and pending:
        session.execute(insert_fn(RealAdmission), pending)


def _write_json_report(json_report: str | None, stats: dict) -> None:
    if not json_report:
        return
    payload = {
        'generated_at': datetime.now(CST).isoformat(timespec='seconds'),
        'parser_version': PARSER_VERSION,
        'dataset': DATASET,
        'files': [_stats_to_json(stats)],
    }
    # --all 时由 main 汇总覆盖本文件；单文件直接写
    files = _JSON_BUFFER.setdefault(str(Path(json_report).resolve()), [])
    files.append(_stats_to_json(stats))
    payload['files'] = files
    Path(json_report).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


_JSON_BUFFER: dict[str, list] = {}


def _stats_to_json(stats: dict) -> dict:
    return {
        'file': stats['file'],
        'province': stats['province'],
        'dry_run': stats['dry_run'],
        'limit': stats['limit'],
        'content_sha256': stats['content_sha256'],
        'parser_version': stats['parser_version'],
        'rows_read': stats['rows_read'],
        'accepted': stats['accepted'],
        'inserted': stats['inserted'],
        'skipped': stats['skipped'],
        'skipped_existing': stats['skipped_existing'],
        'skipped_duplicate': stats['skipped_duplicate'],
        'rejected': stats['rejected'],
        'reject_reasons': dict(stats['reject_reasons']),
        'years': {str(k): v for k, v in stats['years'].items()},
        'subject_types': dict(stats['subject_types']),
        'null_counts': dict(stats['null_counts']),
        'data_version_id': stats['data_version_id'],
        'data_version_current': stats['data_version_current'],
        'deleted_rows': stats['deleted_rows'],
        'retired_versions': stats['retired_versions'],
        'elapsed_seconds': round(stats['elapsed_seconds'], 2),
    }


# --------------------------------------------------------------------------- #
# 命令行
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='SunPath 二期 D2：官方真实投档数据导入器（CSV → real_admissions）',
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--csv', help='单份 CSV 路径（相对/绝对）')
    source.add_argument('--all', action='store_true', help='批量导入三份固定文件（辽宁/贵州/黑龙江）')
    parser.add_argument('--province', help='生源省份（--csv 时必填；--all 时自动推断）')
    parser.add_argument('--limit', type=int, default=None, help='只读取前 N 行数据（调试用）')
    parser.add_argument('--dry-run', action='store_true', help='只解析校验并打印报告，不写数据库')
    parser.add_argument('--database-url', default=None,
                        help='覆盖数据库连接串（测试用，如 sqlite:///C:/tmp/test.db）')
    parser.add_argument('--data-dir', default=None, help='--all 查找 CSV 的优先目录')
    parser.add_argument('--json-report', default=None, help='可选的机器可读报告输出路径')
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit <= 0:
        parser.error('--limit 必须是正整数')
    if args.csv and not args.province:
        parser.error('--csv 模式必须同时给 --province')

    if args.all:
        jobs = [(province, resolve_data_file(filename, args.data_dir))
                for province, filename in DEFAULT_FILES]
    else:
        jobs = [(args.province, Path(args.csv).expanduser())]

    if args.json_report:
        _JSON_BUFFER[str(Path(args.json_report).resolve())] = []

    all_stats = []
    for province, path in jobs:
        stats = import_csv(
            path, province, limit=args.limit, dry_run=args.dry_run,
            database_url=args.database_url, json_report=args.json_report,
        )
        all_stats.append(stats)

    if args.all:
        total_rows = sum(s['rows_read'] for s in all_stats)
        total_accepted = sum(s['accepted'] for s in all_stats)
        total_inserted = sum(s['inserted'] for s in all_stats)
        total_skipped = sum(s['skipped'] for s in all_stats)
        total_rejected = sum(s['rejected'] for s in all_stats)
        print('=' * 78)
        if total_rows == 0 and all(s['skipped_existing'] for s in all_stats):
            print(f'汇总：{len(all_stats)} 份文件均已导入（命中相同哈希的当前版本 DataVersion），'
                  f'本次无新增。重跑不产生重复数据。')
            return 0
        print(f'汇总：文件 {len(all_stats)} 份，数据行数 {total_rows}，有效行 {total_accepted}，'
              f'入库 {total_inserted}，跳过 {total_skipped}，被拒 {total_rejected}')
        print(f"对账：{total_rows} = {total_accepted} + {total_skipped} + {total_rejected}"
              f"（{'一致' if total_rows == total_accepted + total_skipped + total_rejected else '不一致'}）")
    return 0


if __name__ == '__main__':
    sys.exit(main())
