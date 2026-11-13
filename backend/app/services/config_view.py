"""系统参数与接口配置总览（FR-M10-05，只读）。

只读展示后端实际生效的配置，用于演示环境自查；**不回显任何密钥**。
参数修改仍通过 ``backend/.env`` + 重启服务完成（避免把密钥写进数据库或浏览器）。
"""
import sys
from pathlib import Path
from urllib.parse import urlsplit

from app.core.config import BACKEND_DIR, get_settings
from app.services import llm


def mask_email(email: str | None) -> str:
    if not email:
        return '未配置'
    local, _, domain = email.partition('@')
    if not local or not domain:
        return '***'
    return f'{local[:1]}***@{domain}' if len(local) > 1 else f'***@{domain}'


def _database_view(url: str) -> dict:
    parsed = urlsplit(url)
    scheme = (parsed.scheme or '').lower()
    if scheme.startswith('sqlite'):
        path = parsed.path.lstrip('/')
        return {'backend': 'SQLite', 'location': Path(path).name or '内存库', 'secure': True}
    return {
        'backend': scheme.split('+')[0] or 'unknown',
        'host': parsed.hostname or '未配置',
        'database': (parsed.path or '/').lstrip('/') or '未配置',
        'secure': True,  # 不返回用户名与密码
    }


def _ai_provider(host: str) -> str:
    if host in llm.KEYLESS_HOSTS:
        return '免费公共模型通道（无需 API Key）'
    if 'deepseek' in host:
        return 'DeepSeek 官方 API'
    if 'bigmodel' in host:
        return '智谱 AI（GLM）'
    if 'modelscope' in host:
        return 'ModelScope 免费通道'
    return host or '未配置'


def build() -> dict:
    settings = get_settings()
    host = (urlsplit(settings.deepseek_base_url).hostname or '').lower()
    key = bool(settings.deepseek_api_key.get_secret_value().strip())
    keyless = host in llm.KEYLESS_HOSTS
    return {
        'app': {
            'name': 'SunPath 阳光志愿',
            'version': '1.0.0',
            'python': sys.version.split()[0],
            'env_file': (BACKEND_DIR / '.env').exists(),
        },
        'database': _database_view(settings.database_url),
        'security': {
            'jwt_expire_minutes': settings.jwt_expire_minutes,
            'cors_origins': settings.cors_origins,
            'demo_account': bool(settings.demo_email and settings.demo_password),
            'admin_emails': [mask_email(email) for email in settings.admin_emails],
            'admin_count': len(settings.admin_emails),
        },
        'ai': {
            'provider': _ai_provider(host),
            'base_url_host': host or '未配置',
            'model': settings.deepseek_model,
            'model_label': settings.deepseek_model_label,
            'key_configured': key,
            'keyless_channel': keyless,
            'ready': key or keyless,
            'timeout_seconds': settings.deepseek_timeout_seconds,
        },
        'map': {
            'provider': settings.map_provider,
            'tianditu_key_configured': bool(settings.tianditu_web_key),
        },
        'note': '只读总览：敏感值统一隐藏；如需修改请编辑 backend/.env 后重启服务。',
    }
