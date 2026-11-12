"""地图运行时配置：前端运行时向后端取底图来源与天地图 Web 端 Key。

独立运营要点：
- 默认（未配 Key）用**内置省级行政区划示意底图**，零账号、零外部瓦片依赖，可离线运行；
- 部署方想用天地图时，在自己账号下申请 Key 并写入 ``backend/.env`` 的 ``TIANDITU_WEB_KEY``，
  ``MAP_PROVIDER=auto`` 会自动切换；换 Key 只重启后端，前端无需重新构建；
- 未配置时返回 ``provider=schematic``，不会悄悄退回国外瓦片。

安全边界：下发的是浏览器端 Key（前端本来就要用它加载官方 SDK），不是服务端密钥；
接口仍需登录，避免匿名抓取。
"""
from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.security import current_user

router = APIRouter(prefix='/map', tags=['地图配置'], dependencies=[Depends(current_user)])

ATTRIBUTION = {
    'tianditu': '天地图',
    'schematic': '阿里云 DataV GeoAtlas（仅位置示意）',
}


@router.get('/config')
def map_config():
    settings = get_settings()
    key = settings.tianditu_web_key.strip()
    provider = settings.map_provider
    if provider == 'auto':
        provider = 'tianditu' if key else 'schematic'
    ready = bool(key) if provider == 'tianditu' else True
    return {
        'provider': provider,
        'configured': ready,
        'key': key if provider == 'tianditu' else '',
        'attribution': ATTRIBUTION[provider],
        'console_url': 'https://console.tianditu.gov.cn/',
        'note': ('该底图无需任何账号或 Key。'
                 if provider == 'schematic'
                 else ('未配置 TIANDITU_WEB_KEY，地图暂不可用。' if not key
                       else '天地图 Key 来自部署方 backend/.env。')),
    }
