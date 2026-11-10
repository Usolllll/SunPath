"""巡检登记表与脚本常量的一致性测试（不访问网络）。"""
import importlib.util
import json
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((BACKEND_DIR / 'app' / 'data' / 'source_registry.json').read_text(encoding='utf-8'))

spec = importlib.util.spec_from_file_location('patrol_sources', BACKEND_DIR / 'scripts' / 'patrol_sources.py')
patrol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patrol)


class PatrolTests(unittest.TestCase):
    def test_source_ids_unique(self):
        ids = [source['id'] for source in REGISTRY['sources']]
        self.assertEqual(len(ids), len(set(ids)))

    def test_manual_sources_have_compliance_reason(self):
        manual = [source for source in REGISTRY['sources'] if source.get('automation') != 'auto']
        self.assertTrue(manual)
        for source in manual:
            self.assertTrue(any(keyword in source.get('notes', '') for keyword in ('robots', '412', '人工')),
                            source['id'])

    def test_auto_sources_are_public_http(self):
        for source in REGISTRY['sources']:
            if source.get('automation') != 'auto':
                continue
            self.assertTrue(source['url'].startswith(('http://', 'https://')))
            self.assertNotIn('chsi.com.cn', source['url'], '阳光高考不得进入自动巡检')
            self.assertNotIn('lzk.hl.cn', source['url'], '黑龙江 robots 全站禁止，不得自动抓取')

    def test_rate_limit_is_conservative(self):
        self.assertGreaterEqual(patrol.INTERVAL_SECONDS, 1.0)
        self.assertGreaterEqual(patrol.TIMEOUT_SECONDS, 10)


if __name__ == '__main__':
    unittest.main()
