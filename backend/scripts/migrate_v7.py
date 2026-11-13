"""
v7 增量迁移（幂等，可重复执行）：

1. 数据版本审核与发布（FR-M3-05）：data_versions 增加
   review_status / reviewed_by / reviewed_at / review_note；
   既有版本（迁移前导入）统一标记为 approved，避免历史数据被当作待审核。
2. 加分与专项资格（FR-M2-04）：profiles 增加
   bonus_points / bonus_type / special_programs。
3. 招生计划年度对比（FR-M4-03）：为已有专业组补齐 2023–2025 模拟计划行
   （与 2026 年同源、确定性派生；仅演示用，标注模拟数据）。

用法（在 backend 目录）：
  ..\\..\\Python311\\python.exe scripts/migrate_v7.py
  ..\\..\\Python311\\python.exe scripts/migrate_v7.py --dry-run
  ..\\..\\Python311\\python.exe scripts/migrate_v7.py --no-backup
"""
import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402

PROFILE_COLUMNS = (
    ('bonus_points', "INTEGER DEFAULT 0"),
    ('bonus_type', "VARCHAR(30) DEFAULT 'none'"),
    ('special_programs', 'JSON DEFAULT NULL'),
)
VERSION_COLUMNS = (
    ('review_status', "VARCHAR(20) NOT NULL DEFAULT 'pending'"),
    ('reviewed_by', 'VARCHAR(254) DEFAULT NULL'),
    ('reviewed_at', 'DATETIME DEFAULT NULL'),
    ('review_note', 'VARCHAR(200) DEFAULT NULL'),
)
PROVINCES = ['浙江', '江苏', '山东', '广东', '河南', '四川']


def sqlite_path() -> Path:
    url = get_settings().database_url
    if not url.startswith('sqlite:///'):
        raise SystemExit('本脚本只处理本地 SQLite 演示库')
    path = Path(url[len('sqlite:///'):])
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f'PRAGMA table_info({table})')}


def add_columns(connection: sqlite3.Connection, table: str, columns) -> list[str]:
    existing = table_columns(connection, table)
    added = []
    for name, ddl in columns:
        if name not in existing:
            connection.execute(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}')
            added.append(name)
    return added


def backfill_plan_trend(connection: sqlite3.Connection) -> int:
    rows = connection.execute('SELECT group_id, province, year, count FROM enrollments').fetchall()
    current = {(group_id, province, year): count for group_id, province, year, count in rows}
    inserted = 0
    for (group_id, province, year), count in list(current.items()):
        if year != 2026:
            continue
        for target_year, delta in ((2023, -3), (2024, -1), (2025, 2)):
            if (group_id, province, target_year) in current:
                continue
            connection.execute(
                'INSERT INTO enrollments (group_id, province, year, count) VALUES (?, ?, ?, ?)',
                (group_id, province, target_year, max(2, count + delta)),
            )
            inserted += 1
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--no-backup', action='store_true', help='不备份数据库（仅测试/CI 使用）')
    args = parser.parse_args()

    db_path = sqlite_path()
    if not db_path.exists():
        raise SystemExit(f'找不到数据库 {db_path}，请先执行 python -m app.seed')

    if args.dry_run:
        connection = sqlite3.connect(db_path)
        try:
            print('[dry-run] profiles 缺失列:', [n for n, _ in PROFILE_COLUMNS if n not in table_columns(connection, 'profiles')])
            print('[dry-run] data_versions 缺失列:', [n for n, _ in VERSION_COLUMNS if n not in table_columns(connection, 'data_versions')])
            print('[dry-run] enrollments 2026 行数:', connection.execute('SELECT COUNT(*) FROM enrollments WHERE year=2026').fetchone()[0])
        finally:
            connection.close()
        return

    if not args.no_backup:
        backup_dir = BACKEND_DIR / 'backups'
        backup_dir.mkdir(exist_ok=True)
        target = backup_dir / f'sunpath_before_v7_{datetime.now():%Y%m%d_%H%M%S}.db'
        shutil.copy2(db_path, target)
        print(f'已备份 -> {target} ({target.stat().st_size} B)')

    connection = sqlite3.connect(db_path)
    try:
        added_profile = add_columns(connection, 'profiles', PROFILE_COLUMNS)
        added_version = add_columns(connection, 'data_versions', VERSION_COLUMNS)
        if 'review_status' in added_version:
            # 迁移前的版本均已由导入脚本发布过，统一回填为已通过
            connection.execute("UPDATE data_versions SET review_status='approved'")
        inserted = backfill_plan_trend(connection)
        connection.commit()
    finally:
        connection.close()
    print(f'profiles 新增列: {added_profile or "无"}')
    print(f'data_versions 新增列: {added_version or "无"}')
    print(f'补录 2023–2025 模拟招生计划: {inserted} 行')
    print('v7 迁移完成（幂等，可重复执行）。')


if __name__ == '__main__':
    main()
