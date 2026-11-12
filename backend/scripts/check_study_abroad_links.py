#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查留学规划数据里官方入口的可用性（FR-M11-01 的“对接官网”巡检）。

用法（backend 目录下）：
    python scripts/check_study_abroad_links.py [--dry-run] [--timeout 12]

做的事：
- 读取 app/data/study_abroad.json 中考试/地区平台/院校的官方网址；
- 逐个发起请求（跟随跳转，浏览器 UA），记录状态码与检查时间；
- 结果写回 JSON 的 link_status 字段（原子替换，避免写坏数据文件）；
- 403/202/429 视为「可能有人机验证，浏览器可打开」，404/410/5xx 与网络错误标为异常。

只做索引与可用性检查：不抓取正文、不代填申请、不改动任何学校信息。
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

DATA_FILE = Path(__file__).resolve().parents[1] / 'app' / 'data' / 'study_abroad.json'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SunPath-link-check/1.0'


def classify(status: int | None, error: str | None) -> dict:
    if error:
        return {'ok': False, 'status': None, 'note': '网络不可达：' + error[:80]}
    if status is None:
        return {'ok': False, 'status': None, 'note': '未返回状态码'}
    if status < 400:
        return {'ok': True, 'status': status, 'note': '可访问'}
    if status in (202, 403, 429):
        return {'ok': True, 'status': status, 'note': '可能有人机验证，浏览器通常可正常打开'}
    if status in (401,):
        return {'ok': True, 'status': status, 'note': '需要登录，浏览器通常可正常打开'}
    return {'ok': False, 'status': status, 'note': '入口可能已变更，请人工核对'}


def check(client: httpx.Client, url: str) -> dict:
    try:
        response = client.get(url)
        # 少数站点对 HEAD/GET 返回 405/403，再给一次普通请求机会已包含在上面 GET 中。
        return classify(response.status_code, None)
    except Exception as error:  # noqa: BLE001 - 只记录，不让单个坏链接中断巡检
        return classify(None, type(error).__name__)


def iter_urls(data: dict):
    for test in data.get('tests') or []:
        for key in ('official_url', 'registration_url'):
            if test.get(key):
                yield test, key
    for region in data.get('regions') or []:
        if region.get('portal_url'):
            yield region, 'portal_url'
        for school in region.get('schools') or []:
            if school.get('official_url'):
                yield school, 'official_url'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='只打印检查结果，不写回 JSON')
    parser.add_argument('--timeout', type=int, default=12)
    args = parser.parse_args()

    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    checked_at = datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
    client = httpx.Client(timeout=args.timeout, follow_redirects=True, headers={'User-Agent': UA})
    results = []
    try:
        for item, key in iter_urls(data):
            url = item[key]
            outcome = check(client, url)
            outcome['checked_at'] = checked_at
            item.setdefault('link_status', {})[key] = outcome
            results.append((item.get('name') or item.get('label') or item.get('code'), key, url, outcome))
    finally:
        client.close()

    ok = sum(1 for _, _, _, outcome in results if outcome['ok'])
    for name, key, url, outcome in results:
        flag = 'OK ' if outcome['ok'] else 'BAD'
        print(f"{flag} {str(name)[:34]:36} {str(outcome['status']):>4}  {url}  ({outcome['note']})")
    print(f'\nchecked {len(results)} links, ok {ok}, problems {len(results) - ok}')
    print('checked_at:', checked_at)

    if args.dry_run:
        print('dry-run: 未写回 JSON')
        return 0 if ok == len(results) else 1

    data.setdefault('_meta', {})['link_checked_at'] = checked_at
    payload = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    directory = DATA_FILE.parent
    fd, temp_path = tempfile.mkstemp(prefix='study_abroad.', suffix='.json', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(payload)
        os.replace(temp_path, DATA_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    print('written:', DATA_FILE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
