from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import get_settings, BACKEND_DIR

url = get_settings().database_url
if url.startswith('sqlite:///') and not url.startswith('sqlite:////'):
    filename = url.removeprefix('sqlite:///')
    if filename != ':memory:':
        url = 'sqlite:///' + (BACKEND_DIR / filename).as_posix()
engine = create_engine(url, pool_pre_ping=True, connect_args={'check_same_thread': False} if url.startswith('sqlite') else {})

if url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def _sqlite_pragmas(dbapi_connection, _record):
        # 深分页/大结果集排序时 SQLite 会落临时文件；演示环境临时目录可能不可写，
        # 改为内存临时表，避免 "unable to open database file"。
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA temp_store=MEMORY')
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as db:
        yield db
