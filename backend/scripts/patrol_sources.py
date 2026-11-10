"""官方数据源巡检（骨架）：列表页/公告页哈希差分 → 变更告警 → 版本表待复核。

用法（在 backend 目录）：
  ..\\..\\Python311\\python.exe scripts/patrol_sources.py
  ..\\..\\Python311\\python.exe scripts/patrol_sources.py --no-db

规则：
- 只巡检 registry 中 automation=auto 的源；manual 源（黑龙江 robots 禁爬、阳光高考 412）只记录不抓取。
- 串行 + 1.5s 间隔（约 0.5 QPS），带 UA，不绕过任何反爬，不跟随登录。
- 内容哈希与上次巡检不同 → 标 CHANGED，并在 data_versions 记一条「待复核」，绝不自动改库。
"""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import httpx  # noqa: E402

REGISTRY = BACKEND_DIR / 'app' / 'data' / 'source_registry.json'
STATE_DIR = BACKEND_DIR / 'state'
REPORT_DIR = BACKEND_DIR / 'reports'
STATE_FILE = STATE_DIR / 'source_checks.json'
UA = 'SunPath-patrol/0.1 (+course-project; contact: local)'
INTERVAL_SECONDS = 1.5
TIMEOUT_SECONDS = 20


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return {}
    return {}


def _fetch(source: dict) -> dict:
    """优先 httpx（带一次重试）；个别站点 Set-Cookie 含非 ASCII 时 httpx 会报编码错，回退 urllib。"""
    attempts = 0
    last_error = None
    for follow in (True, False):
        attempts += 1
        try:
            response = httpx.get(source['url'], timeout=TIMEOUT_SECONDS, follow_redirects=follow,
                                 headers={'User-Agent': UA, 'Accept': 'text/html,application/json;q=0.9,*/*;q=0.8'})
            return {'status': response.status_code, 'content': response.content, 'url': str(response.url),
                    'headers': dict(response.headers), 'backend': 'httpx', 'attempts': attempts}
        except Exception as error:  # 网络异常或编码异常如实记录
            last_error = error
            time.sleep(INTERVAL_SECONDS)

    attempts += 1
    try:
        import urllib.request
        request = urllib.request.Request(source['url'], headers={'User-Agent': UA,
                                                                'Accept': 'text/html,application/json;q=0.9,*/*;q=0.8'})
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return {'status': response.status, 'content': response.read(), 'url': response.geturl(),
                    'headers': dict(response.headers), 'backend': 'urllib', 'attempts': attempts}
    except Exception as error:
        raise error from last_error


def check_source(source: dict) -> dict:
    started = time.time()
    result = {
        'id': source['id'], 'dataset': source['dataset'], 'province': source.get('province'),
        'url': source['url'], 'update_window': source.get('update_window'),
        'checked_at': datetime.now().astimezone().isoformat(timespec='seconds'),
    }
    try:
        response = _fetch(source)
        body = response['content']
        result.update(
            status=response['status'], bytes=len(body), final_url=response['url'],
            content_sha256=hashlib.sha256(body).hexdigest(),
            etag=response['headers'].get('etag'), last_modified=response['headers'].get('last-modified'),
            elapsed_ms=int((time.time() - started) * 1000), attempts=response['attempts'],
            backend=response['backend'],
        )
        result['ok'] = 200 <= response['status'] < 300
        result['hint'] = '列表页内容可能含时间戳，哈希变化需人工打开原文确认'
    except Exception as error:  # 网络异常如实记录，不降级为“正常”
        result.update(ok=False, status=None, error=f'{type(error).__name__}: {str(error)[:160]}',
                      elapsed_ms=int((time.time() - started) * 1000))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-db', action='store_true', help='只巡检不写版本表')
    parser.add_argument('--only', default='', help='只巡检指定 id，逗号分隔')
    args = parser.parse_args()

    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    sources = registry['sources']
    if args.only:
        wanted = {item.strip() for item in args.only.split(',') if item.strip()}
        sources = [item for item in sources if item['id'] in wanted]

    STATE_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)
    state = load_state()
    report = []
    changed = []

    for source in sources:
        if source.get('automation') != 'auto':
            report.append({'id': source['id'], 'dataset': source['dataset'], 'skipped': True,
                           'reason': source.get('notes', '按登记表不自动抓取'), 'url': source['url']})
            print(f"[跳过] {source['id']} {source['dataset']}（{source.get('notes', 'manual')}）")
            continue
        result = check_source(source)
        previous = state.get(source['id'], {})
        result['changed'] = bool(result.get('content_sha256') and previous.get('content_sha256')
                                 and result['content_sha256'] != previous['content_sha256'])
        result['first_seen'] = not bool(previous.get('content_sha256'))
        if result['changed']:
            changed.append(result)
        state[source['id']] = {key: result.get(key) for key in ('status', 'bytes', 'content_sha256', 'checked_at', 'ok')}
        report.append(result)
        flag = '⚠ CHANGED' if result['changed'] else ('首见' if result.get('first_seen') else '无变化')
        status = result.get('status') or result.get('error', '')[:40]
        print(f"[巡检] {source['id']:<8} {str(status):<5} {result.get('bytes', 0):>8} B  {flag}")
        time.sleep(INTERVAL_SECONDS)

    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = REPORT_DIR / f'patrol_{stamp}.json'
    report_path.write_text(json.dumps({'checked_at': stamp, 'items': report}, ensure_ascii=False, indent=2), encoding='utf-8')

    if not args.no_db and changed:
        _record_pending(changed)

    print(f"\n巡检完成：{len(report)} 个源，哈希变化 {len(changed)} 个")
    print(f"报告：{report_path}")
    for item in changed:
        print(f"  ⚠ {item['dataset']}（{item['province'] or '全国'}）→ 人工打开 {item['url']} 复核")
    return 0


def _record_pending(changed: list) -> None:
    """变更源写入 data_versions，标记待人工复核（不自动改数值）。"""
    try:
        from app.core.database import SessionLocal
        from app.models.entities import DataVersion
    except Exception as error:
        print(f"[警告] 无法连接数据库，跳过版本登记：{error}")
        return
    from sqlalchemy import select
    with SessionLocal() as db:
        for item in changed:
            db.add(DataVersion(
                dataset='巡检:' + item['dataset'], province=item.get('province'), exam_year=None,
                source_url=item['url'], attachment_url=None, published_at=None,
                fetched_at=item['checked_at'], content_sha256=item['content_sha256'],
                parser_version='patrol@0.1.0', doc_status='待复核', is_current=True, row_count=None,
                note='巡检发现内容哈希变化，需人工打开原文复核后再导入',
            ))
        db.commit()
    print(f"[版本表] 已登记 {len(changed)} 条待复核记录")


if __name__ == '__main__':
    raise SystemExit(main())
