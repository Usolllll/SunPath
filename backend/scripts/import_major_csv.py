#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「专业级」官方 CSV 追加导入 real_admissions（M4 专业级数据）。

与 ``scripts/import_real.py`` 的区别：本导入器**只追加、不删除**已有行。
同一运行内按 ORM 唯一键去重，跨运行/跨文件用「已有键集合」跳过已存在行，
因此三份文件（985 三省招生计划、河北历史/物理投档）互相覆盖的年份/省份
不会被误删，重复执行也不会产生重复数据。

统一表头（18 列，UTF-8 BOM；河北两份为 17 列，缺少「选科要求」）：
    学校名称,全国院校代码,生源省份,招生年份,招考科类,招生类型,投档轮次,
    专业组代号,专业组名称,具体专业,最低分,最低位次,最高分,平均分,
    实际录取人数,[选科要求],来源链接,备注

用法（backend 目录下，Python 3.11）：
    python scripts/import_major_csv.py --csv <a.csv> [--csv <b.csv> ...] [--dry-run]
        [--province 河北] [--dataset 专业级投档] [--database-url sqlite:///...]
        [--json-report out.json] [--batch-size 2000]

provenance：每份文件写一行 DataVersion（dataset 自动识别：文件名含「招生计划」→
招生计划，否则 → 专业级投档；province 取 --province 或文件内主要省份），
并把同 dataset+province 的旧 is_current 置 False。
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

PARSER_VERSION = 'major-csv@1.0.0'
DATASET_PLAN = '招生计划'
DATASET_TICK = '专业级投档'
DOC_STATUS = '已导入'
CST = timezone(timedelta(hours=8))

DEFAULT_BATCH_SIZE = 2000
MAX_SCHOOL_LEN = 80
MAX_TEXT_LEN = 120          # group_name / major_name / required_subjects
MAX_NOTE_LEN = 500
MAX_URL_LEN = 500
MIN_YEAR, MAX_YEAR = 2020, 2030
MIN_SCORE, MAX_SCORE = 0, 750
EMPTY_MARKERS = {'', '—', '-', '--', '－', '/', '\\', '无', '未公开', '暂无'}

HEADER_ALIASES = {
    'school_name': ('学校名称', '学校名称(院校)', '院校代号及名称', '院校名称', '招生院校'),
    'national_code': ('全国院校代码', '院校国标代码', '国标代码', '全国院校标代码'),
    'province': ('生源省份', '省份', '生源省'),
    'exam_year': ('招生年份', '年份', '录取年份', '招生年度'),
    'subject_type': ('招考科类', '科类', '招生科类', '选考科类'),
    'admission_type': ('招生类型', '计划性质', '招生性质'),
    'batch': ('批次', '录取批次', '招生批次'),
    'round_no': ('投档轮次', '轮次', '投档批次'),
    'group_code': ('专业组代号', '专业组代码', '院校专业组代号', '专业组号'),
    'group_name': ('专业组名称', '院校专业组名称', '专业组'),
    'major_name': ('具体专业', '专业名称', '专业'),
    'min_score': ('最低分', '投档最低分', '最低投档分'),
    'min_rank': ('最低位次', '投档最低位次', '最低排名'),
    'max_score': ('最高分', '最高投档分'),
    'avg_score': ('平均分', '平均投档分'),
    'actual_count': ('实际录取人数', '录取人数'),
    'plan_count': ('计划数', '招生计划数', '计划人数'),
    'required_subjects': ('选科要求', '选考科目要求', '选考要求', '再选科目要求'),
    'source_url': ('来源链接', '来源网址', '来源', '原文链接'),
    'note': ('备注', '说明'),
}
_ALIAS_INDEX = {alias: canonical for canonical, aliases in HEADER_ALIASES.items() for alias in aliases}
_WS_RE = re.compile(r'[\s\u00a0\u3000]+')
_SCHOOL_CODE_RE = re.compile(r'^[A-Za-zＡ-Ｚａ-ｚ]{1,2}\d{2,5}[\s\-_/、,，:：.]*')
_INT_RE = re.compile(r'^[+-]?\d+$')
_NATIONAL_CODE_RE = re.compile(r'^\d{5}$')
_DATE_DASH_RE = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
_DATE_COMPACT_RE = re.compile(r'(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)')

_SESSION_CACHE: dict[str, tuple] = {}


# --------------------------------------------------------------------------- #
# 文本 / 数值 / 来源工具
# --------------------------------------------------------------------------- #
def clean_text(value) -> str:
    if value is None:
        return ''
    return _WS_RE.sub(' ', str(value).replace('\ufeff', '')).strip()


def _norm_header(value) -> str:
    return re.sub(r'\s+', '', clean_text(value).replace('（', '(').replace('）', ')')).lower()


def map_headers(fieldnames) -> dict:
    mapping: dict[str, str] = {}
    for header in fieldnames or []:
        canonical = _ALIAS_INDEX.get(_norm_header(header))
        if canonical and canonical not in mapping:
            mapping[canonical] = header
    return mapping


def _pick(row, mapping, canonical) -> str:
    header = mapping.get(canonical)
    return row.get(header) if header else None


def _is_empty(value) -> bool:
    return clean_text(value) in EMPTY_MARKERS


def strip_school_code(name: str) -> str:
    name = (name or '').strip()
    previous = None
    while previous != name:
        previous = name
        name = _SCHOOL_CODE_RE.sub('', name)
    return name.strip()


def parse_int(value) -> tuple[int | None, str | None]:
    """空值/占位符 → (None, None)；非整数 → (None, '非整数')。"""
    text = clean_text(value)
    if text in EMPTY_MARKERS:
        return None, None
    if not _INT_RE.match(text):
        return None, '非整数'
    return int(text), None


def truncate_text(value: str, limit: int) -> tuple[str | None, bool]:
    text = clean_text(value)
    if not text:
        return None, False
    if len(text) <= limit:
        return text, False
    return text[: limit - 1] + '…', True


def parse_published_at(source_url) -> str | None:
    url = clean_text(source_url)
    if not url:
        return None
    for match in _DATE_DASH_RE.finditer(url):
        year, month, day = (int(part) for part in match.groups())
        if 2000 <= year <= MAX_YEAR and 1 <= month <= 12 and 1 <= day <= 31:
            return f'{year:04d}-{month:02d}-{day:02d}'
    for match in _DATE_COMPACT_RE.finditer(url):
        year, month, day = (int(part) for part in match.groups())
        if 2000 <= year <= MAX_YEAR and 1 <= month <= 12 and 1 <= day <= 31:
            return f'{year:04d}-{month:02d}-{day:02d}'
    return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def local_source_url(path: Path) -> str:
    return 'local://' + path.name


def infer_dataset(path: Path) -> str:
    name = path.name
    if '招生计划' in name or '计划' in name:
        return DATASET_PLAN
    if '投档' in name:
        return DATASET_TICK
    return DATASET_TICK


# --------------------------------------------------------------------------- #
# 数据库连接（惰性导入，测试可覆盖）
# --------------------------------------------------------------------------- #
def _looks_like_absolute_sqlite(url: str) -> bool:
    if not url.startswith('sqlite:///'):
        return False
    path = url[len('sqlite:///'):]
    return path.startswith('/') or (len(path) > 2 and path[1] == ':')


def _make_override_engine(database_url: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import event

    from app.core.database import Base
    from app.models.entities import RealAdmission, DataVersion  # noqa: F401  注册 ORM

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={'check_same_thread': False, 'timeout': 30} if database_url.startswith('sqlite') else {},
    )

    @event.listens_for(engine, 'connect')
    def _set_busy_timeout(dbapi_connection, _record):  # pragma: no cover - 连接级设置
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA busy_timeout = 30000')
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False), engine


def get_session_factory(database_url: str | None = None):
    """返回 (session_factory, RealAdmission, DataVersion)。"""
    override = database_url
    if not override:
        env_url = os.environ.get('DATABASE_URL', '')
        if env_url and _looks_like_absolute_sqlite(env_url):
            override = env_url
    key = override or '__default__'
    if key in _SESSION_CACHE:
        return _SESSION_CACHE[key]
    if override:
        session_factory, _engine = _make_override_engine(override)
        from app.models.entities import DataVersion, RealAdmission
    else:
        from sqlalchemy import event, text

        from app.core.database import Base, SessionLocal, engine
        from app.models.entities import DataVersion, RealAdmission

        Base.metadata.create_all(engine)

        @event.listens_for(engine, 'connect')
        def _set_busy_timeout(dbapi_connection, _record):  # pragma: no cover
            cursor = dbapi_connection.cursor()
            cursor.execute('PRAGMA busy_timeout = 30000')
            cursor.close()

        session_factory = SessionLocal
    result = (session_factory, RealAdmission, DataVersion)
    _SESSION_CACHE[key] = result
    return result


# --------------------------------------------------------------------------- #
# 行解析 / 校验
# --------------------------------------------------------------------------- #
def build_record(row, mapping, forced_province: str | None, path: Path,
                 file_sha: str, fetched_at: str, fallback_source: str) -> tuple[dict | None, str | None, dict]:
    """返回 (record, reject_reason, info)。"""
    info = {'truncated': []}
    if None in row:
        return None, '列数不符(多列)', info
    if any(value is None for value in row.values()):
        return None, '列数不符(缺列)', info

    school = strip_school_code(clean_text(_pick(row, mapping, 'school_name')))
    if not school:
        return None, '学校名为空', info
    if len(school) > MAX_SCHOOL_LEN:
        return None, f'学校名超长(>{MAX_SCHOOL_LEN})', info

    province = clean_text(_pick(row, mapping, 'province'))
    if forced_province:
        if province and province != forced_province:
            return None, '省份与参数不一致', info
        province = forced_province
    if not province:
        return None, '省份为空', info

    year, year_error = parse_int(_pick(row, mapping, 'exam_year'))
    if year_error:
        return None, '招生年份非整数', info
    if year is None:
        return None, '招生年份缺失', info
    if not (MIN_YEAR <= year <= MAX_YEAR):
        return None, f'招生年份越界({MIN_YEAR}-{MAX_YEAR})', info

    subject_type, _ = truncate_text(_pick(row, mapping, 'subject_type'), 20)
    if not subject_type:
        return None, '招考科类为空', info

    scores = {}
    dropped_fields: list[str] = []
    for canonical, label in (('min_score', '最低分'), ('max_score', '最高分'), ('avg_score', '平均分')):
        value, error = parse_int(_pick(row, mapping, canonical))
        if canonical == 'min_score':
            # 最低分是核心字段：非法直接拒绝该行
            if error:
                return None, f'{label}非整数', info
            if value is not None and not (MIN_SCORE <= value <= MAX_SCORE):
                return None, f'{label}越界({MIN_SCORE}-{MAX_SCORE})', info
        else:
            # 最高分/平均分是辅助字段：源表偶见串列（如填成位次），置空保留该行
            if error or (value is not None and not (MIN_SCORE <= value <= MAX_SCORE)):
                dropped_fields.append(label)
                value = None
        scores[canonical] = value
    info['dropped_fields'] = dropped_fields

    min_rank, rank_error = parse_int(_pick(row, mapping, 'min_rank'))
    if rank_error:
        return None, '最低位次非整数', info
    if min_rank is not None and min_rank <= 0:
        return None, '最低位次非正整数', info

    counts = {}
    for canonical, label in (('actual_count', '实际录取人数'), ('plan_count', '计划数')):
        value, error = parse_int(_pick(row, mapping, canonical))
        if error:
            return None, f'{label}非整数', info
        if value is not None and value < 0:
            return None, f'{label}为负数', info
        counts[canonical] = value

    national_code = clean_text(_pick(row, mapping, 'national_code'))
    if national_code and not _NATIONAL_CODE_RE.match(national_code):
        national_code = ''

    group_code, _ = truncate_text(_pick(row, mapping, 'group_code'), 30)
    group_name, group_truncated = truncate_text(_pick(row, mapping, 'group_name'), MAX_TEXT_LEN)
    major_name, major_truncated = truncate_text(_pick(row, mapping, 'major_name'), MAX_TEXT_LEN)
    if group_truncated:
        info['truncated'].append('group_name')
    if major_truncated:
        info['truncated'].append('major_name')
    required, required_truncated = truncate_text(_pick(row, mapping, 'required_subjects'), MAX_TEXT_LEN)
    if required_truncated:
        info['truncated'].append('required_subjects')
    admission_type, _ = truncate_text(_pick(row, mapping, 'admission_type'), 20)
    batch, _ = truncate_text(_pick(row, mapping, 'batch'), 30)
    round_no, _ = truncate_text(_pick(row, mapping, 'round_no'), 20)

    row_source = clean_text(_pick(row, mapping, 'source_url'))
    source_url = row_source or fallback_source or local_source_url(path)
    if len(source_url) > MAX_URL_LEN:
        source_url = source_url[:MAX_URL_LEN]

    note_parts = []
    raw_note = clean_text(_pick(row, mapping, 'note'))
    if raw_note:
        note_parts.append(raw_note)
    if dropped_fields:
        note_parts.append('原始' + '、'.join(dropped_fields) + '超出 0-750 已置空')
    note = '；'.join(note_parts) or None
    if info['truncated']:
        suffix = '文本字段超长已截断：' + '、'.join(info['truncated'])
        note = f'{note}；{suffix}' if note else suffix
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
        'content_sha256': file_sha,
        'parser_version': PARSER_VERSION,
        'doc_status': DOC_STATUS,
        'note': note,
    }
    return record, None, info


def dedupe_key(record: dict) -> tuple:
    return (
        record['province'], record['exam_year'], record['subject_type'],
        record['batch'] or '', record['round_no'] or '', record['group_code'] or '',
        record['group_name'] or '', record['major_name'] or '', record['school_name'],
        record['admission_type'] or '',
    )


def _intern_key(record: dict) -> tuple:
    return tuple(sys.intern(str(part)) for part in dedupe_key(record))


def load_existing_keys(session_factory, RealAdmission) -> set[tuple]:
    """一次读出库里已有的唯一键集合（用 intern 压内存），用于跨运行/跨文件去重。"""
    from sqlalchemy import select

    keys: set[tuple] = set()
    with session_factory() as session:
        statement = select(
            RealAdmission.province, RealAdmission.exam_year, RealAdmission.subject_type,
            RealAdmission.batch, RealAdmission.round_no, RealAdmission.group_code,
            RealAdmission.group_name, RealAdmission.major_name, RealAdmission.school_name,
            RealAdmission.admission_type,
        )
        for row in session.execute(statement).yield_per(5000):
            keys.add(tuple('' if value is None else sys.intern(str(value)) for value in row))
    return keys


# --------------------------------------------------------------------------- #
# 单文件导入
# --------------------------------------------------------------------------- #
def _scan_file(path: Path, mapping: dict, forced_province: str | None, file_sha: str,
               fetched_at: str, fallback_source: str, stats: dict) -> set[tuple]:
    """第一遍流式扫描：统计解析/非法/同文件重复，返回同文件内有效唯一键集合。"""
    file_keys: set[tuple] = set()
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f'CSV 没有表头：{path}')
        stats['headers'] = list(reader.fieldnames)
        if 'school_name' not in mapping or 'exam_year' not in mapping:
            raise ValueError(f'CSV 表头缺少学校名称/招生年份：{reader.fieldnames}')
        for row in reader:
            stats['parsed'] += 1
            record, reason, info = build_record(
                row, mapping, forced_province, path, file_sha, fetched_at, fallback_source
            )
            if reason:
                stats['invalid'] += 1
                stats['invalid_reasons'][reason] += 1
                if len(stats['invalid_samples']) < 3:
                    label = clean_text(_pick(row, mapping, 'school_name'))[:40] or '?'
                    year_text = clean_text(_pick(row, mapping, 'exam_year')) or '?'
                    stats['invalid_samples'].append(f'{reason}｜学校={label}｜年份={year_text}')
                continue
            for field in info.get('dropped_fields') or []:
                stats['dropped_fields'][field] += 1
            stats['years'][record['exam_year']] += 1
            stats['subjects'][record['subject_type']] += 1
            stats['provinces'][record['province']] += 1
            stats['source_urls'][record['source_url']] += 1
            key = _intern_key(record)
            if key in file_keys:
                stats['skipped_duplicate'] += 1
                continue
            file_keys.add(key)
    return file_keys


def _fallback_source(urls: Counter) -> str:
    if not urls:
        return ''
    return urls.most_common(1)[0][0]


def _write_file(session_factory, RealAdmission, DataVersion, path: Path, stats: dict,
                file_keys: set[tuple], existing_keys: set[tuple], mapping: dict,
                forced_province: str | None, file_sha: str, fetched_at: str,
                fallback_source: str, dataset: str, batch_size: int,
                dry_run: bool) -> dict:
    """第二遍流式写入（追加 + 跳过已存在键）；返回写入计数。"""
    from sqlalchemy import func, select

    inserted = 0
    skipped_existing = 0
    if dry_run:
        # dry-run：只统计「本轮会写入多少、因已存在跳过多少」
        if existing_keys:
            for key in file_keys:
                if key in existing_keys:
                    skipped_existing += 1
        stats['inserted'] = len(file_keys) - skipped_existing
        stats['skipped_existing'] = skipped_existing
        return {'inserted': stats['inserted'], 'skipped_existing': skipped_existing}

    session = session_factory()
    try:
        from sqlalchemy import func, insert, select, text

        pending: list[dict] = []
        inserted = 0
        province_key = forced_province or stats['provinces'].most_common(1)[0][0]

        with session.begin():
            # 服务可能在读库；SQLite 写锁等待 30s 而不是立刻报 locked
            try:
                session.execute(text('PRAGMA busy_timeout = 30000'))
            except Exception:  # pragma: no cover - 非 sqlite 时忽略
                pass
            before = session.scalar(select(func.count()).select_from(RealAdmission)) or 0

            with path.open('r', encoding='utf-8-sig', newline='') as handle:
                reader = csv.DictReader(handle)
                seen_in_pass: set[tuple] = set()
                for row in reader:
                    record, reason, _info = build_record(
                        row, mapping, forced_province, path, file_sha, fetched_at, fallback_source
                    )
                    if reason:
                        continue
                    key = _intern_key(record)
                    if key in seen_in_pass:
                        continue  # 同文件重复行：第一遍已计入 skipped_duplicate，这里静默跳过
                    seen_in_pass.add(key)
                    if key in existing_keys:
                        skipped_existing += 1
                        continue
                    pending.append(record)
                    existing_keys.add(key)
                    if len(pending) >= batch_size:
                        session.execute(insert(RealAdmission), pending)
                        inserted += len(pending)
                        pending.clear()
                if pending:
                    session.execute(insert(RealAdmission), pending)
                    inserted += len(pending)
                    pending.clear()

            session.flush()
            after = session.scalar(select(func.count()).select_from(RealAdmission)) or 0
            inserted = after - before

            # DataVersion provenance：同 dataset+province+文件哈希 的版本只留一行，重复运行复用
            current = session.scalars(
                select(DataVersion).where(
                    DataVersion.dataset == dataset,
                    DataVersion.province == province_key,
                    DataVersion.content_sha256 == file_sha,
                    DataVersion.parser_version == PARSER_VERSION,
                ).order_by(DataVersion.id.desc())
            ).first()
            if current is not None:
                stats['data_version_id'] = current.id
                stats['data_version_current'] = bool(current.is_current)
                stats['data_version_reused'] = True
                # 文件哈希没变但主来源修正过（例如首次只看了文件前部）时，校正 provenance
                if stats['source_url'] and current.source_url != stats['source_url'][:MAX_URL_LEN]:
                    current.source_url = stats['source_url'][:MAX_URL_LEN]
                    current.published_at = parse_published_at(stats['source_url'])
            else:
                stats['retired_versions'] = session.query(DataVersion).filter(
                    DataVersion.dataset == dataset,
                    DataVersion.province == province_key,
                    DataVersion.is_current.is_(True),
                ).update({'is_current': False}, synchronize_session=False)
                year_counts = ', '.join(f'{year}:{count}' for year, count in sorted(stats['years'].items()))
                province_counts = ', '.join(
                    f'{province}:{count}' for province, count in stats['provinces'].most_common()
                )
                version = DataVersion(
                    dataset=dataset,
                    province=province_key,
                    exam_year=None,
                    source_url=stats['source_url'] or local_source_url(path),
                    attachment_url=None,
                    published_at=parse_published_at(stats['source_url']),
                    fetched_at=fetched_at,
                    content_sha256=file_sha,
                    parser_version=PARSER_VERSION,
                    doc_status=DOC_STATUS,
                    is_current=True,
                    row_count=inserted,
                    note=(
                        f'本地文件：{path.name}；{dataset}；年度 {year_counts}；'
                        f'省份 {province_counts}'
                    )[:200],
                )
                session.add(version)
                session.flush()
                stats['data_version_id'] = version.id
                stats['data_version_current'] = True
        stats['inserted'] = inserted
        stats['skipped_existing'] = skipped_existing
        return {'inserted': inserted, 'skipped_existing': skipped_existing}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def import_file(path: Path, *, forced_province: str | None, dataset_override: str | None,
                dry_run: bool, database_url: str | None, batch_size: int,
                existing_keys: set[tuple] | None, session_factory, RealAdmission,
                DataVersion, out=print) -> dict:
    started = datetime.now(CST)
    file_sha = sha256_file(path)
    fetched_at = started.isoformat(timespec='seconds')
    dataset = dataset_override or infer_dataset(path)
    stats: dict = {
        'file': str(path), 'dataset': dataset, 'sha256': file_sha, 'dry_run': dry_run,
        'parsed': 0, 'inserted': 0, 'skipped_duplicate': 0, 'skipped_existing': 0,
        'invalid': 0, 'invalid_reasons': Counter(), 'invalid_samples': [],
        'dropped_fields': Counter(),
        'years': Counter(), 'subjects': Counter(), 'provinces': Counter(),
        'source_urls': Counter(), 'source_url': '',
        'data_version_id': None, 'data_version_current': None, 'data_version_reused': False,
        'retired_versions': 0, 'headers': [],
    }

    # 第一遍：统计「文件内出现最多的来源链接」作为行内来源为空时的回退
    # （逐行来源 URL 计数在下面的正式扫描里统计）
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f'CSV 没有表头：{path}')
        mapping = map_headers(reader.fieldnames)
        for row in reader:
            url = clean_text(_pick(row, mapping, 'source_url'))
            if url:
                stats['source_urls'][url] += 1
    stats['source_url'] = _fallback_source(stats['source_urls'])
    stats['source_urls'] = Counter()  # 逐行 URL 计数在下面正式扫描里统计

    file_keys = _scan_file(path, mapping, forced_province, file_sha, fetched_at,
                           stats['source_url'], stats)
    if existing_keys is None:
        existing_keys = set()
    _write_file(session_factory, RealAdmission, DataVersion, path, stats, file_keys,
                existing_keys, mapping, forced_province, file_sha, fetched_at,
                stats['source_url'], dataset, batch_size, dry_run)

    stats['elapsed_seconds'] = (datetime.now(CST) - started).total_seconds()
    _print_file_report(stats, out=out)
    return stats


def _print_file_report(stats: dict, out=print) -> None:
    out('=' * 78)
    out(f"导入报告：{Path(stats['file']).name}")
    out(f"  dataset={stats['dataset']}  sha256={stats['sha256'][:16]}…  "
        f"{'[dry-run] 不写库' if stats['dry_run'] else ''}")
    out(f"  解析={stats['parsed']}  写入={stats['inserted']}  "
        f"跳过(已存在)={stats['skipped_existing']}  跳过(同文件重复)={stats['skipped_duplicate']}  "
        f"非法={stats['invalid']}")
    if stats['years']:
        out('  年度分布：' + '，'.join(f'{year}:{count}' for year, count in sorted(stats['years'].items())))
    if len(stats['provinces']) > 1:
        out('  省份分布：' + '，'.join(f'{p}:{c}' for p, c in stats['provinces'].most_common()))
    if stats['subjects']:
        out('  科类分布：' + '，'.join(f'{s}:{c}' for s, c in stats['subjects'].most_common()))
    if stats['invalid_reasons']:
        out('  非法原因：' + '；'.join(f'{reason}:{count}' for reason, count in stats['invalid_reasons'].most_common()))
    for sample in stats['invalid_samples']:
        out(f'  非法抽样：{sample}')
    if stats['dropped_fields']:
        out('  辅助字段置空（超出 0-750 或非整数）：'
            + '；'.join(f'{field}:{count}' for field, count in stats['dropped_fields'].most_common()))
    if stats.get('data_version_id') is not None:
        out(f"  DataVersion id={stats['data_version_id']} is_current={stats['data_version_current']}"
            f"{'（复用既有版本）' if stats.get('data_version_reused') else ''}"
            f"  旧版本置非当前 {stats.get('retired_versions', 0)} 条")
    out(f"  耗时 {stats['elapsed_seconds']:.2f}s")
    out('')


# --------------------------------------------------------------------------- #
# 命令行
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='专业级官方 CSV 追加导入 real_admissions（幂等、不删除）')
    parser.add_argument('--csv', action='append', required=True, help='CSV 路径，可重复多次')
    parser.add_argument('--province', default=None, help='强制省份（不给则取行内「生源省份」）')
    parser.add_argument('--dataset', default=None, help='DataVersion.dataset 覆盖（招生计划 / 专业级投档）')
    parser.add_argument('--dry-run', action='store_true', help='只统计，不写数据库')
    parser.add_argument('--database-url', default=None, help='覆盖数据库连接串（测试用）')
    parser.add_argument('--json-report', default=None, help='机器可读报告输出路径')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE, help='批量插入行数')
    return parser


def _db_province_counts(session_factory, RealAdmission) -> dict[str, int]:
    from sqlalchemy import func, select

    with session_factory() as session:
        rows = session.execute(
            select(RealAdmission.province, func.count()).group_by(RealAdmission.province)
            .order_by(RealAdmission.province)
        ).all()
    return {province: count for province, count in rows}


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.batch_size <= 0:
        parser.error('--batch-size 必须为正整数')
    paths = [Path(item).expanduser() for item in args.csv]
    for path in paths:
        if not path.is_file():
            parser.error(f'CSV 不存在：{path}')

    session_factory = RealAdmission = DataVersion = None
    existing_keys: set[tuple] = set()
    if not args.dry_run:
        session_factory, RealAdmission, DataVersion = get_session_factory(args.database_url)
        existing_keys = load_existing_keys(session_factory, RealAdmission)

    all_stats = []
    for path in paths:
        all_stats.append(import_file(
            path, forced_province=args.province, dataset_override=args.dataset,
            dry_run=args.dry_run, database_url=args.database_url, batch_size=args.batch_size,
            existing_keys=existing_keys, session_factory=session_factory,
            RealAdmission=RealAdmission, DataVersion=DataVersion,
        ))

    totals = {
        'parsed': sum(item['parsed'] for item in all_stats),
        'inserted': sum(item['inserted'] for item in all_stats),
        'skipped_duplicate': sum(item['skipped_duplicate'] for item in all_stats),
        'skipped_existing': sum(item['skipped_existing'] for item in all_stats),
        'invalid': sum(item['invalid'] for item in all_stats),
    }
    db_counts = {}
    if not args.dry_run:
        db_counts = _db_province_counts(session_factory, RealAdmission)
        print('DB 内各省真实数据行数：' + '，'.join(f'{p}:{c}' for p, c in db_counts.items()))
    print('=' * 78)
    print(f"汇总：文件 {len(all_stats)} 份，解析 {totals['parsed']}，写入 {totals['inserted']}，"
          f"跳过(已存在) {totals['skipped_existing']}，跳过(同文件重复) {totals['skipped_duplicate']}，"
          f"非法 {totals['invalid']}")
    print(f"对账：{totals['parsed']} = {totals['inserted']} + {totals['skipped_existing']} + "
          f"{totals['skipped_duplicate']} + {totals['invalid']}"
          f"（{'一致' if totals['parsed'] == totals['inserted'] + totals['skipped_existing'] + totals['skipped_duplicate'] + totals['invalid'] else '不一致'}）")

    if args.json_report:
        payload = {
            'generated_at': datetime.now(CST).isoformat(timespec='seconds'),
            'parser_version': PARSER_VERSION,
            'dry_run': args.dry_run,
            'totals': totals,
            'db_province_counts': db_counts,
            'files': [{
                'file': item['file'], 'dataset': item['dataset'], 'sha256': item['sha256'],
                'parsed': item['parsed'], 'inserted': item['inserted'],
                'skipped_duplicate': item['skipped_duplicate'],
                'skipped_existing': item['skipped_existing'],
                'invalid': item['invalid'],
                'invalid_reasons': dict(item['invalid_reasons']),
                'dropped_fields': dict(item['dropped_fields']),
                'years': {str(y): c for y, c in item['years'].items()},
                'provinces': dict(item['provinces']),
                'data_version_id': item['data_version_id'],
                'data_version_current': item['data_version_current'],
            } for item in all_stats],
        }
        Path(args.json_report).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
