"""
v5 增量迁移：批次与填报时间配置表（batch_configs）+ 默认两个批次。幂等，可重复执行。

用法（在 backend 目录）：
  ..\\..\\Python311\\python.exe scripts/migrate_v5.py
  ..\\..\\Python311\\python.exe scripts/migrate_v5.py --dry-run
  ..\\..\\Python311\\python.exe scripts/migrate_v5.py --no-backup   # 仅测试/CI 使用
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.entities import BatchConfig  # noqa: E402
from app.services.batches import DEFAULT_BATCHES, ensure_defaults  # noqa: E402


def sqlite_path() -> Path:
    url = get_settings().database_url
    if not url.startswith('sqlite:///'):
        raise SystemExit('本脚本只处理本地 SQLite 演示库')
    path = Path(url[len('sqlite:///'):])
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--no-backup', action='store_true', help='不备份数据库（仅测试/CI 使用）')
    args = parser.parse_args()

    db_path = sqlite_path()
    if not db_path.exists():
        raise SystemExit(f'找不到数据库 {db_path}，请先执行 python -m app.seed')

    default_names = [name for name, _sort_order in DEFAULT_BATCHES]
    if args.dry_run:
        print(f'[dry-run] 将建表 batch_configs 并补齐默认批次 {default_names}')
        return

    if not args.no_backup:
        backup_dir = BACKEND_DIR / 'backups'
        backup_dir.mkdir(exist_ok=True)
        target = backup_dir / f'sunpath_before_v5_{datetime.now():%Y%m%d_%H%M%S}.db'
        shutil.copy2(db_path, target)
        print(f'已备份 -> {target} ({target.stat().st_size} B)')

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        inserted = ensure_defaults(db)
        db.commit()
        total = int(db.scalar(select(func.count()).select_from(BatchConfig)) or 0)
        rows = list(db.scalars(select(BatchConfig).order_by(BatchConfig.sort_order, BatchConfig.name)))
        summary = [(row.name, row.sort_order, bool(row.active)) for row in rows]
    print(f'新增默认批次 {inserted} 个；batch_configs 共 {total} 行；当前配置 {summary}；迁移完成。')


if __name__ == '__main__':
    main()
