#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「一分一段表」CSV 合并进 ``app/data/score_segments.json``（M4-02）。

CSV 至少包含三列：分数、人数、累计人数（支持 UTF-8 BOM）。生成的数据为
「示例/导入数据」，文件 _meta 会如实标注 data_mode 与 note；上线前必须用
省考试院官方一分一段表替换。

用法（backend 目录下，Python 3.11）：
    python scripts/import_score_segment.py --province 浙江 --year 2026 \
        --subject-type 综合改革 --source-url https://www.zjzs.net/ \
        --published-at 2026-06-25 --csv ./一分一段.csv [--total-candidates 300000]

行为：
- 直接读写 JSON，不连数据库；
- 同省同年重复导入会覆盖旧分段（幂等）；其他省份/年份原样保留；
- 校验分数严格降序、累计人数严格递增，不合法打印原因并以非 0 退出；
- 成功后打印 segments 条数、区间与总人数。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_FILE = BACKEND_DIR / 'app' / 'data' / 'score_segments.json'
DEFAULT_META = {
    'purpose': '按分数查累计人数与位次位置（一分一段表），用于志愿填报时判断考生位次参考，不预测录取结果。',
    'data_mode': '示例',
    'note': '示例数据，上线前必须用省考试院官方一分一段表替换。',
    'updated_at': '2026-11',
}

HEADER_ALIASES = {
    'score': ('分数', '分数(分)', 'score', '投档分'),
    'count': ('人数', '本段人数', 'count', '该分人数'),
    'cumulative': ('累计人数', '累计', 'cumulative', '累计位次'),
}
_INT_RE = re.compile(r'^[+-]?\d+$')


def _norm_header(value) -> str:
    return re.sub(r'\s+', '', str(value or '').replace('（', '(').replace('）', ')')).lower()


def _alias_index() -> dict:
    return {alias: field for field, aliases in HEADER_ALIASES.items() for alias in aliases}


def map_headers(fieldnames) -> dict:
    mapping: dict[str, str] = {}
    aliases = _alias_index()
    for header in fieldnames or []:
        field = aliases.get(_norm_header(header))
        if field and field not in mapping:
            mapping[field] = header
    return mapping


def _int_cell(row: dict, header: str | None, label: str, line_no: int) -> int:
    raw = (row.get(header) or '').strip() if header else ''
    if not _INT_RE.match(raw):
        raise ValueError(f'第 {line_no} 行「{label}」不是整数：{raw!r}')
    return int(raw)


def read_segments(csv_path: Path) -> list[dict]:
    """读取并校验 CSV；返回 [{'score','count','cumulative'}, ...]（分数降序）。"""
    if not csv_path.is_file():
        raise ValueError(f'CSV 不存在：{csv_path}')
    with csv_path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError('CSV 没有表头')
        mapping = map_headers(reader.fieldnames)
        missing = [field for field in ('score', 'count', 'cumulative') if field not in mapping]
        if missing:
            raise ValueError(f'CSV 缺少必要列 {missing}；实际表头：{reader.fieldnames}')
        segments: list[dict] = []
        for line_no, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f'第 {line_no} 行列数多于表头')
            if all(not (row.get(column) or '').strip() for column in reader.fieldnames):
                continue  # 跳过空行
            score = _int_cell(row, mapping['score'], '分数', line_no)
            count = _int_cell(row, mapping['count'], '人数', line_no)
            cumulative = _int_cell(row, mapping['cumulative'], '累计人数', line_no)
            if not (0 <= score <= 750):
                raise ValueError(f'第 {line_no} 行分数越界（0–750）：{score}')
            if count <= 0:
                raise ValueError(f'第 {line_no} 行人数必须为正整数：{count}')
            if cumulative <= 0:
                raise ValueError(f'第 {line_no} 行累计人数必须为正整数：{cumulative}')
            segments.append({'score': score, 'count': count, 'cumulative': cumulative})
    if not segments:
        raise ValueError('CSV 没有数据行')
    for index in range(1, len(segments)):
        previous, current = segments[index - 1], segments[index]
        if current['score'] >= previous['score']:
            raise ValueError(f'分数必须严格降序：{previous["score"]} → {current["score"]}')
        if current['cumulative'] <= previous['cumulative']:
            raise ValueError(
                f'累计人数必须随分数降低严格递增：{previous["score"]}({previous["cumulative"]}) '
                f'→ {current["score"]}({current["cumulative"]})'
            )
    return segments


def load_payload(data_file: Path) -> dict:
    """读现有 JSON；不存在时用默认 meta 初始化。"""
    if not data_file.is_file():
        return {'_meta': dict(DEFAULT_META), 'provinces': {}}
    try:
        payload = json.loads(data_file.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f'现有数据文件无法解析：{data_file}（{error}）') from error
    if not isinstance(payload, dict) or not isinstance(payload.get('provinces'), dict):
        raise ValueError(f'现有数据文件结构不符合约定（需要 provinces 对象）：{data_file}')
    payload.setdefault('_meta', dict(DEFAULT_META))
    return payload


def merge(payload: dict, province: str, year: int, entry: dict) -> dict:
    """同省同年覆盖（幂等），其他数据不动。"""
    provinces = payload.setdefault('provinces', {})
    province_block = provinces.setdefault(str(province), {})
    if not isinstance(province_block, dict):
        province_block = {}
        provinces[str(province)] = province_block
    province_block[str(year)] = entry
    return payload


def write_payload(payload: dict, data_file: Path) -> None:
    data_file.parent.mkdir(parents=True, exist_ok=True)
    temp_path = data_file.with_name(data_file.name + '.tmp')
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp_path, data_file)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='一分一段 CSV → app/data/score_segments.json')
    parser.add_argument('--province', required=True, help='生源省份，如 浙江')
    parser.add_argument('--year', type=int, required=True, help='招生年份，如 2026')
    parser.add_argument('--subject-type', required=True, help='科类，如 综合改革 / 物理类 / 历史类')
    parser.add_argument('--source-url', default='', help='官方一分一段公告链接（可空）')
    parser.add_argument('--published-at', default='', help='官方发布时间 YYYY-MM-DD（可空）')
    parser.add_argument('--csv', required=True, help='一分一段 CSV 路径')
    parser.add_argument('--total-candidates', type=int, default=None,
                        help='该省高考人数（用于 percentile；默认取区间最低分的累计人数）')
    parser.add_argument('--data-file', default=str(DEFAULT_DATA_FILE),
                        help='目标 JSON（默认 app/data/score_segments.json）')
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (2020 <= args.year <= 2030):
        parser.error('--year 必须在 2020–2030 之间')
    if args.total_candidates is not None and args.total_candidates <= 0:
        parser.error('--total-candidates 必须为正整数')

    csv_path = Path(args.csv).expanduser()
    data_file = Path(args.data_file).expanduser()
    try:
        segments = read_segments(csv_path)
        payload = load_payload(data_file)
    except ValueError as error:
        print(f'[ERROR] {error}', file=sys.stderr)
        return 1

    top, bottom = segments[0], segments[-1]
    total_candidates = args.total_candidates or bottom['cumulative']
    if total_candidates < bottom['cumulative']:
        print(f'[ERROR] --total-candidates({total_candidates}) 小于累计人数({bottom["cumulative"]})',
              file=sys.stderr)
        return 1

    existing_entry = payload.get('provinces', {}).get(str(args.province), {}).get(str(args.year))
    meta = payload.setdefault('_meta', dict(DEFAULT_META))
    meta['data_mode'] = '示例'
    meta.setdefault('note', DEFAULT_META['note'])
    meta['updated_at'] = '2026-11'
    if not meta.get('note'):
        meta['note'] = DEFAULT_META['note']

    entry = {
        'subject_type': args.subject_type,
        'source_url': args.source_url,
        'published_at': args.published_at,
        'total_candidates': total_candidates,
        'segments': segments,
    }
    merge(payload, args.province, args.year, entry)
    try:
        write_payload(payload, data_file)
    except OSError as error:
        print(f'[ERROR] 写入失败：{error}', file=sys.stderr)
        return 1

    action = '已覆盖' if existing_entry else '新增'
    print(f'{action} {args.province} {args.year}：segments {len(segments)} 条，'
          f'分数区间 {top["score"]}–{bottom["score"]}，'
          f'区间最低分累计人数 {bottom["cumulative"]}，'
          f'该省高考人数（percentile 分母）{total_candidates}；'
          f'目标文件 {data_file}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
