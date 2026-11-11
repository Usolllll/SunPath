"""
v3 增量迁移：方案批次/状态字段 + 收藏表 + 审计表。幂等，可重复执行。

用法（在 backend 目录）：
  ..\\..\\Python311\\python.exe scripts/migrate_v3.py
"""
import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base, engine  # noqa: E402
from app.core.config import get_settings  # noqa: E402
import app.models.entities  # noqa: E402,F401

COLUMNS = {
    'plans': [
        ('batch', "VARCHAR(20) DEFAULT '本科批'"),
        ('status', "VARCHAR(20) DEFAULT 'draft'"),
        ('submitted_at', 'DATETIME'),
        ('idempotency_key', 'VARCHAR(64)'),
    ],
}
NEW_TABLES = ('favorites', 'audit_logs')


def sqlite_path() -> Path:
    url = get_settings().database_url
    if not url.startswith('sqlite:///'):
        raise SystemExit('本脚本只处理本地 SQLite 演示库')
    path = Path(url[len('sqlite:///'):])
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    db_path = sqlite_path()
    if not db_path.exists():
        raise SystemExit(f'找不到数据库 {db_path}，请先执行 python -m app.seed')

    if not args.dry_run:
        backup_dir = BACKEND_DIR / 'backups'
        backup_dir.mkdir(exist_ok=True)
        target = backup_dir / f'sunpath_before_v3_{datetime.now():%Y%m%d_%H%M%S}.db'
        shutil.copy2(db_path, target)
        print(f'已备份 -> {target} ({target.stat().st_size} B)')

    connection = sqlite3.connect(db_path)
    added = 0
    for table, columns in COLUMNS.items():
        existing = {row[1] for row in connection.execute(f'PRAGMA table_info({table})')}
        for name, ddl in columns:
            if name in existing:
                continue
            if args.dry_run:
                print(f'[dry-run] ALTER TABLE {table} ADD COLUMN {name} {ddl}')
            else:
                connection.execute(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}')
            added += 1
    if not args.dry_run:
        connection.execute("UPDATE plans SET batch=COALESCE(batch,'本科批'), status=COALESCE(status,'draft')")
    connection.commit()
    connection.close()

    if args.dry_run:
        print(f'[dry-run] 需新增 {added} 列')
        return

    Base.metadata.create_all(engine)
    connection = sqlite3.connect(db_path)
    connection.execute(
        'CREATE INDEX IF NOT EXISTS ix_real_admission_province_year_school '
        'ON real_admissions (province, exam_year, school_name, min_rank)'
    )
    connection.commit()
    counts = {table: connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in NEW_TABLES}
    connection.close()
    print(f'新增列 {added} 个；新表行数 {counts}；迁移完成。')


if __name__ == '__main__':
    main()
