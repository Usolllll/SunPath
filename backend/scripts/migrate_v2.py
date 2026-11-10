"""v2 schema 迁移：备份 → 加列 → 建新表 → 回填映射。幂等，可重复执行。

用法（在 backend 目录）：
  ..\\..\\Python311\\python.exe scripts/migrate_v2.py
  ..\\..\\Python311\\python.exe scripts/migrate_v2.py --dry-run
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
import app.models.entities  # noqa: E402,F401  确保新表注册到 metadata
from app.services.enrichment import level_scores, city_tiers  # noqa: E402

COLUMNS = {
    'universities': [
        ('level_tier', 'INTEGER'),
        ('city_tier', 'INTEGER'),
        ('transfer_friendly', 'INTEGER'),
        ('transfer_notes', 'VARCHAR(300)'),
        ('transfer_source_url', 'VARCHAR(500)'),
        ('transfer_year', 'INTEGER'),
        ('official_url', 'VARCHAR(500)'),
    ],
    'major_groups': [
        ('tuition_type', 'VARCHAR(20)'),
        ('accommodation', 'INTEGER'),
        ('duration_years', 'INTEGER DEFAULT 4'),
        ('major_category', 'VARCHAR(20)'),
        ('degree_type', 'VARCHAR(20)'),
        ('cost_source_url', 'VARCHAR(500)'),
        ('cost_year', 'INTEGER'),
    ],
    'profiles': [
        ('priority_mode', "VARCHAR(10) DEFAULT 'balanced'"),
        ('interests', 'JSON'),
        ('budget_total', 'INTEGER'),
        ('physical', 'JSON'),
        ('intent_types', 'JSON'),
    ],
    'plans': [
        ('mode', 'VARCHAR(10)'),
        ('weights_snapshot', 'JSON'),
        ('budget_snapshot', 'JSON'),
    ],
}


def sqlite_path() -> Path:
    url = get_settings().database_url
    if not url.startswith('sqlite:///'):
        raise SystemExit('本脚本只处理本地 SQLite 演示库，当前 DATABASE_URL 不是 sqlite')
    raw = url[len('sqlite:///'):]
    path = Path(raw)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--no-backup', action='store_true')
    args = parser.parse_args()

    db_path = sqlite_path()
    if not db_path.exists():
        raise SystemExit(f'找不到数据库 {db_path}，请先执行 python -m app.seed')

    print(f'数据库: {db_path}')
    if not args.no_backup and not args.dry_run:
        backup_dir = BACKEND_DIR / 'backups'
        backup_dir.mkdir(exist_ok=True)
        target = backup_dir / f'sunpath_before_v2_{datetime.now():%Y%m%d_%H%M%S}.db'
        shutil.copy2(db_path, target)
        print(f'已备份 -> {target} ({target.stat().st_size} B)')

    conn = sqlite3.connect(db_path)
    added, skipped = [], []
    for table, columns in COLUMNS.items():
        existing = table_columns(conn, table)
        if not existing:
            print(f'[跳过] 表 {table} 不存在（将由 create_all 新建）')
            continue
        for name, ddl in columns:
            if name in existing:
                skipped.append(f'{table}.{name}')
                continue
            if args.dry_run:
                print(f'[dry-run] ALTER TABLE {table} ADD COLUMN {name} {ddl}')
            else:
                conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}')
            added.append(f'{table}.{name}')
    conn.commit()

    if args.dry_run:
        conn.close()
        print(f'\n[dry-run] 需新增 {len(added)} 列; 已存在 {len(skipped)} 列')
        return

    Base.metadata.create_all(engine)
    new_tables = [t for t in ('real_admissions', 'data_versions', 'major_catalog', 'employment_summaries')]
    counts = {}
    for table in new_tables:
        counts[table] = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]

    levels = {}
    cities = {}
    try:
        levels = level_scores()
        cities = city_tiers()
    except FileNotFoundError as error:
        print(f'[警告] 映射表暂缺（{error.filename}），跳过层次/城市回填；补齐后重跑本脚本即可。')
    tier_updates = 0
    for name, score in levels.items():
        tier_updates += conn.execute('UPDATE universities SET level_tier=? WHERE level=? AND (level_tier IS NULL OR level_tier<>?)',
                                     (score, name, score)).rowcount
    city_updates = 0
    for name, tier in cities.items():
        city_updates += conn.execute('UPDATE universities SET city_tier=? WHERE city=? AND (city_tier IS NULL OR city_tier<>?)',
                                     (tier, name, tier)).rowcount
    group_rows = conn.execute(
        "UPDATE major_groups SET tuition_type=COALESCE(tuition_type,'公办'), accommodation=COALESCE(accommodation,1000),"
        " duration_years=COALESCE(duration_years,4), cost_year=COALESCE(cost_year,2026)").rowcount
    conn.commit()
    conn.close()

    print(f'\n新增列 {len(added)} 个: ' + (', '.join(added) if added else '无'))
    print(f'已存在列 {len(skipped)} 个')
    print(f'新表行数: {counts}')
    print(f'回填: 院校层次 {tier_updates} 行, 城市分级 {city_updates} 行, 专业组预算默认值 {group_rows} 行')
    print('迁移完成。')


if __name__ == '__main__':
    main()
