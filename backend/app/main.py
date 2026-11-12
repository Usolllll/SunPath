from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.database import engine
from app.api import auth, data, favorites, plans, chat, ops, process, notices, messages

@asynccontextmanager
async def lifespan(app):
    yield
    engine.dispose()

app = FastAPI(title='SunPath 阳光志愿 API', version='1.0.0', lifespan=lifespan, description='MVP 模拟招生数据；不提供真实录取概率。')
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=True, allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key'])
app.include_router(auth.router, prefix='/api')
app.include_router(data.router, prefix='/api')
app.include_router(plans.router, prefix='/api')
app.include_router(chat.router, prefix='/api')
app.include_router(favorites.router, prefix='/api')
app.include_router(ops.router, prefix='/api')
app.include_router(process.router, prefix='/api')
app.include_router(notices.router, prefix='/api')
app.include_router(messages.router, prefix='/api')

@app.get('/api/health', tags=['运行状态'])
def health():
    from sqlalchemy import text
    with engine.connect() as connection:
        connection.execute(text('SELECT 1'))
    return {'status': 'ok', 'data_mode': 'simulated'}
