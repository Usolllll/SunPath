from pathlib import Path
from functools import lru_cache
from pydantic import Field, SecretStr, field_validator
from urllib.parse import urlsplit
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
    deepseek_api_key: SecretStr = SecretStr('')
    deepseek_base_url: str = 'https://api.deepseek.com'
    deepseek_model: str = 'deepseek-flash'
    deepseek_model_label: str = 'DeepSeek-V4.1-Flash-1017'
    deepseek_timeout_seconds: int = Field(default=60, ge=10, le=120)

    @field_validator('deepseek_base_url')
    @classmethod
    def validate_model_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('DEEPSEEK_BASE_URL 必须为不含凭据和查询参数的 HTTPS 接口地址')
        return value.rstrip('/')

    @field_validator('deepseek_model', 'deepseek_model_label')
    @classmethod
    def validate_model_name(cls, value):
        if not value.strip() or len(value) > 150:
            raise ValueError('模型标识必须为 1–150 个字符')
        return value.strip()

    @field_validator('jwt_secret')
    @classmethod
    def reject_placeholder(cls, value):
        if value.startswith('REPLACE_'):
            raise ValueError('请在 backend/.env 中设置随机 JWT_SECRET')
        return value

@lru_cache
def get_settings():
    return Settings()
