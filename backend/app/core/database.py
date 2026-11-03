from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import get_settings, BACKEND_DIR

url = get_settings().database_url
if url.startswith('sqlite:///') and not url.startswith('sqlite:////'):
    filename = url.removeprefix('sqlite:///')
    if filename != ':memory:':
        url = 'sqlite:///' + (BACKEND_DIR / filename).as_posix()
engine = create_engine(url, pool_pre_ping=True, connect_args={'check_same_thread': False} if url.startswith('sqlite') else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as db:
        yield db
