"""地图运行时配置（/api/map/config）与 TIANDITU_WEB_KEY / MAP_PROVIDER 校验测试。

复用 test_workflow 的临时库模式；配置由 get_settings 注入，测试不依赖本机 .env。
"""
import secrets
import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    import test_workflow  # noqa: F401  先设置临时 DATABASE_URL，避免污染开发库
except ImportError:
    from tests import test_workflow  # noqa: F401

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import map as map_api
from app.core.config import Settings
from app.main import app
from app.seed import seed

KEY = '0fb497820eb803f28b63abb60d3c48be'


class MapConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def login(self):
        email = f'{secrets.token_hex(6)}@map-test.cn'
        response = self.client.post('/api/auth/register',
                                    json={'email': email, 'password': 'TestPassword123!', 'name': '地图测试'})
        self.assertEqual(response.status_code, 201, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def config(self, headers, key, provider='auto'):
        settings = SimpleNamespace(tianditu_web_key=key, map_provider=provider)
        with patch.object(map_api, 'get_settings', return_value=settings):
            return self.client.get('/api/map/config', headers=headers)

    def test_requires_login(self):
        self.assertEqual(self.client.get('/api/map/config').status_code, 401)

    def test_auto_uses_schematic_without_key(self):
        headers = self.login()
        response = self.config(headers, '')
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload['provider'], 'schematic')
        self.assertTrue(payload['configured'])
        self.assertEqual(payload['key'], '')
        self.assertIn('DataV', payload['attribution'])
        self.assertIn('无需任何账号', payload['note'])
        self.assertTrue({'console_url'} <= set(payload))

    def test_auto_uses_tianditu_when_key_configured(self):
        headers = self.login()
        payload = self.config(headers, KEY).json()
        self.assertEqual(payload['provider'], 'tianditu')
        self.assertTrue(payload['configured'])
        self.assertEqual(payload['key'], KEY)
        self.assertEqual(payload['attribution'], '天地图')

    def test_explicit_provider_wins(self):
        headers = self.login()
        forced_schematic = self.config(headers, KEY, provider='schematic').json()
        self.assertEqual(forced_schematic['provider'], 'schematic')
        self.assertEqual(forced_schematic['key'], '')

        forced_tianditu = self.config(headers, '', provider='tianditu').json()
        self.assertEqual(forced_tianditu['provider'], 'tianditu')
        self.assertFalse(forced_tianditu['configured'])
        self.assertIn('未配置', forced_tianditu['note'])

    def test_settings_validate_map_options(self):
        base = {'database_url': 'sqlite://', 'jwt_secret': 'x' * 64}
        self.assertEqual(Settings(**base, tianditu_web_key='').tianditu_web_key, '')
        self.assertEqual(Settings(**base, tianditu_web_key=KEY.upper()).tianditu_web_key, KEY)
        self.assertEqual(Settings(**base).map_provider, 'auto')
        self.assertEqual(Settings(**base, map_provider='SCHEMATIC').map_provider, 'schematic')
        for bad in ['short', 'z' * 32, 'a' * 31, 'a' * 33]:
            with self.assertRaises(ValidationError):
                Settings(**base, tianditu_web_key=bad)
        with self.assertRaises(ValidationError):
            Settings(**base, map_provider='amap')


if __name__ == '__main__':
    unittest.main()
