"""地图运行时配置（FR 之外的部署配置项）：前端运行时向后端取天地图 Web 端 Key。

独立运营要点：
- Key 属于**部署方自己的天地图账号**，不随前端源码/构建产物分发；
- 换 Key 只需改 ``backend/.env`` 的 ``TIANDITU_WEB_KEY`` 并重启后端，前端无需重新构建；
- 未配置时返回 ``configured=false``，前端显示「天地图服务待启用」，不影响院校列表与查询。

安全边界：这里下发的是浏览器端 Key（前端本来就要用它加载官方 SDK），
不是服务端密钥；接口仍需登录，避免匿名抓取。
"""
from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.security import current_user

router = APIRouter(prefix='/map', tags=['地图配置'], dependencies=[Depends(current_user)])


@router.get('/config')
def map_config():
    settings = get_settings()
    key = settings.tianditu_web_key.strip()
    return {
        'provider': 'tianditu',
        'configured': bool(key),
        'key': key,
        'attribution': '天地图',
        'console_url': 'https://console.tianditu.gov.cn/',
    }
