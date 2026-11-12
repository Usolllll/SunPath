"""
v6 增量迁移：留学规划目标表（study_abroad_targets）。幂等，可重复执行。

用法（在 backend 目录）：
  ..\\..\\Python311\\python.exe scripts/migrate_v6.py
  ..\\..\\Python311\\python.exe scripts/migrate_v6.py --dry-run
  ..\\..\\Python311\\python.exe scripts/migrate_v6.py --no-backup   # 仅测试/CI 使用
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
from app.models.entities import StudyAbroadTarget  # noqa: E402

TABLE = 'study_abroad_targets'


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

    if args.dry_run:
        print(f'[dry-run] 将建表并校验 {TABLE}（留学规划目标，无默认数据）')
        return

    if not args.no_backup:
        backup_dir = BACKEND_DIR / 'backups'
        backup_dir.mkdir(exist_ok=True)
        target = backup_dir / f'sunpath_before_v6_{datetime.now():%Y%m%d_%H%M%S}.db'
        shutil.copy2(db_path, target)
        print(f'已备份 -> {target} ({target.stat().st_size} B)')

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        total = int(db.scalar(select(func.count()).select_from(StudyAbroadTarget)) or 0)
        columns = [column.name for column in StudyAbroadTarget.__table__.columns]
    print(f'{TABLE} 共 {total} 行；列 {columns}；迁移完成。')


if __name__ == '__main__':
    main()
