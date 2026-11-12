"""地图运行时配置（/api/map/config）与 TIANDITU_WEB_KEY 校验测试。

复用 test_workflow 的临时库模式；Key 由 get_settings 注入，测试不依赖本机 .env。
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

    def config(self, headers, key):
        with patch.object(map_api, 'get_settings', return_value=SimpleNamespace(tianditu_web_key=key)):
            return self.client.get('/api/map/config', headers=headers)

    def test_requires_login(self):
        self.assertEqual(self.client.get('/api/map/config').status_code, 401)

    def test_unconfigured_and_configured_responses(self):
        headers = self.login()
        empty = self.config(headers, '')
        self.assertEqual(empty.status_code, 200, empty.text)
        payload = empty.json()
        self.assertEqual(payload['provider'], 'tianditu')
        self.assertFalse(payload['configured'])
        self.assertEqual(payload['key'], '')
        self.assertTrue({'attribution', 'console_url'} <= set(payload))

        key = '0fb497820eb803f28b63abb60d3c48be'
        ready = self.config(headers, key)
        self.assertEqual(ready.status_code, 200, ready.text)
        self.assertTrue(ready.json()['configured'])
        self.assertEqual(ready.json()['key'], key)

    def test_settings_validate_tianditu_key(self):
        base = {'database_url': 'sqlite://', 'jwt_secret': 'x' * 64}
        self.assertEqual(Settings(**base, tianditu_web_key='').tianditu_web_key, '')
        self.assertEqual(Settings(**base, tianditu_web_key='A' * 32).tianditu_web_key, 'a' * 32)
        for bad in ['short', 'z' * 32, 'a' * 31, 'a' * 33]:
            with self.assertRaises(ValidationError):
                Settings(**base, tianditu_web_key=bad)


if __name__ == '__main__':
    unittest.main()
