"""SQLite 备份 / 恢复 + data_versions 版本导出（FR-M10-02）。

用法（在 backend 目录）：
  ..\\..\\Python311\\python.exe scripts/backup_restore.py backup [--out DIR]
  ..\\..\\Python311\\python.exe scripts/backup_restore.py restore --file PATH --yes [--out DIR]

- 备份：用 sqlite3 在线备份 API 复制当前库（不裸拷贝正在写入的文件），
  同时把 data_versions 导出为 JSON，并生成含 sha256 / size / 时间的 manifest。
- 恢复：没有 --yes 一律拒绝；恢复前会自动再备份当前库（默认 backend/backups/）。
- 仅支持 sqlite:/// 数据库，路径解析规则与 app.core.database 一致（相对 backend 目录）。
"""
import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


def database_path() -> Path:
    """从 DATABASE_URL 解析 SQLite 文件路径（相对路径按 backend 目录解析）。"""
    from app.core.config import BACKEND_DIR as backend_dir, get_settings
    url = get_settings().database_url
    if not url.startswith('sqlite:///'):
        raise SystemExit('本脚本只支持 sqlite:/// 数据库')
    filename = url[len('sqlite:///'):]
    if not filename or filename == ':memory:':
        raise SystemExit('不支持内存数据库或空数据库路径')
    path = Path(filename)
    if not path.is_absolute():
        path = Path(backend_dir) / path
    return path.resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def export_data_versions(db_file: Path) -> list[dict]:
    """从备份/当前库里导出 data_versions 台账（表不存在时返回空列表）。"""
    try:
        with sqlite3.connect(db_file) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute('SELECT * FROM data_versions ORDER BY id').fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error:
        return []


def backup(out_dir: Path | None = None) -> dict:
    source = database_path()
    if not source.exists():
        raise SystemExit(f'数据库不存在：{source}')
    target_dir = Path(out_dir).resolve() if out_dir else BACKEND_DIR / 'backups'
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup_file = target_dir / f'sunpath_{stamp}.db'
    versions_file = target_dir / f'sunpath_{stamp}_data_versions.json'
    manifest_file = target_dir / f'sunpath_{stamp}_manifest.json'

    # sqlite3 在线备份：一致快照，避免直接复制正在写入的文件
    with sqlite3.connect(source) as source_connection, sqlite3.connect(backup_file) as backup_connection:
        source_connection.backup(backup_connection)

    versions = export_data_versions(backup_file)
    created_at = datetime.now().astimezone().isoformat()
    versions_file.write_text(json.dumps({'created_at': created_at, 'items': versions},
                                        ensure_ascii=False, indent=2), encoding='utf-8')
    size = backup_file.stat().st_size
    digest = sha256_file(backup_file)
    manifest = {
        'created_at': created_at,
        'database': str(source),
        'backup_file': str(backup_file),
        'size_bytes': size,
        'sha256': digest,
        'data_versions_file': str(versions_file),
        'data_versions_count': len(versions),
    }
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'command': 'backup', 'backup_file': str(backup_file), 'manifest_file': str(manifest_file),
            'data_versions_file': str(versions_file), 'size_bytes': size, 'sha256': digest,
            'data_versions_count': len(versions)}


def _looks_like_sqlite(path: Path) -> bool:
    with path.open('rb') as handle:
        return handle.read(16) == b'SQLite format 3\x00'


def restore(file: Path, out_dir: Path | None = None) -> dict:
    source_backup = Path(file).resolve()
    if not source_backup.exists():
        raise SystemExit(f'备份文件不存在：{source_backup}')
    target = database_path()
    if source_backup == target:
        raise SystemExit('备份文件与当前数据库是同一文件，已拒绝')
    if not _looks_like_sqlite(source_backup):
        raise SystemExit(f'不是有效的 SQLite 备份文件：{source_backup}')

    pre_backup = None
    if target.exists():
        pre_backup = backup(out_dir)['backup_file']
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_backup, target)
    digest = sha256_file(target)
    return {'command': 'restore', 'restored_to': str(target), 'from': str(source_backup),
            'pre_backup': pre_backup, 'sha256': digest, 'size_bytes': target.stat().st_size}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='SunPath SQLite 备份 / 恢复（FR-M10-02）')
    subcommands = parser.add_subparsers(dest='command', required=True)

    backup_parser = subcommands.add_parser('backup', help='备份当前数据库并导出 data_versions')
    backup_parser.add_argument('--out', type=Path, default=None, help='备份输出目录（默认 backend/backups）')

    restore_parser = subcommands.add_parser('restore', help='用备份覆盖当前数据库（必须 --yes）')
    restore_parser.add_argument('--file', type=Path, required=True, help='要恢复的 .db 备份文件')
    restore_parser.add_argument('--yes', action='store_true', help='确认覆盖当前数据库')
    restore_parser.add_argument('--out', type=Path, default=None,
                                help='恢复前自动备份当前库的输出目录（默认 backend/backups）')

    args = parser.parse_args(argv)
    if args.command == 'backup':
        result = backup(args.out)
    else:
        if not args.yes:
            print('拒绝执行：恢复会覆盖当前数据库，确认无误后请加 --yes', file=sys.stderr)
            return 2
        result = restore(args.file, args.out)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
