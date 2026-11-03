from pathlib import Path
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / '.env', env_file_encoding='utf-8', extra='ignore')
    database_url: str
    jwt_secret: str = Field(min_length=32)
    jwt_expire_minutes: int = Field(default=1440, ge=5, le=10080)
    cors_origins: list[str] = ['http://localhost:5173', 'http://127.0.0.1:5173']
    demo_email: str | None = None
    demo_password: str | None = None

    @field_validator('jwt_secret')
    @classmethod
    def reject_placeholder(cls, value):
        if value.startswith('REPLACE_'):
            raise ValueError('请在 backend/.env 中设置随机 JWT_SECRET')
        return value

@lru_cache
def get_settings():
    return Settings()
