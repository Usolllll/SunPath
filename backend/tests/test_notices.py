"""M8：政策公告 / 站内消息中心 / 订阅偏好（临时 SQLite，不连开发库）。

复用 test_workflow 的临时库模式（先 `import test_workflow` 让它在导入 app 前设置 DATABASE_URL）；
公告内容读取真实 app/data/announcements.json，消息/订阅全部走临时库。

运行（backend 目录下）：
    ..\\..\\Python311\\python.exe -m unittest tests.test_notices -v
"""
import json
import secrets
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

try:
    import test_workflow  # noqa: F401  先设置临时 DATABASE_URL，避免污染开发库
except ImportError:
    from tests import test_workflow  # noqa: F401

from fastapi.testclient import TestClient

from app.core.database import engine
from app.main import app
from app.seed import seed

BACKEND_DIR = Path(__file__).resolve().parents[1]
ANNOUNCEMENTS = json.loads((BACKEND_DIR / 'app' / 'data' / 'announcements.json').read_text(encoding='utf-8'))['items']
PROFILE = {'province': '浙江', 'exam_year': 2026, 'score': 628, 'rank': 22580,
           'subjects': ['物理', '化学', '生物'], 'regions': ['浙江', '江苏', '上海'],
           'majors': ['计算机', '电子信息']}
DEFAULT_SUBSCRIPTION = {'types': ['collection', 'plan'], 'channel': 'site', 'lead_days': 3}


class NoticesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()

    def setUp(self):
        self.user, self.headers = self.account('消息测试')
        self.client.put('/api/auth/profile', headers=self.headers, json=PROFILE)

    # ---------------------------------------------------------------- helpers
    def account(self, name='消息测试'):
        email = f'{secrets.token_hex(8)}@test.cn'
        response = self.client.post('/api/auth/register',
                                    json={'email': email, 'password': 'TestPassword123!', 'name': name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['user'], {'Authorization': f"Bearer {response.json()['access_token']}"}

    def save_plan(self, name='消息方案'):
        ids = [item['id'] for item in
               self.client.get('/api/recommendations', headers=self.headers).json()['items'][:3]]
        response = self.client.post('/api/plans', headers=self.headers, json={'name': name, 'group_ids': ids})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def messages(self, **params):
        response = self.client.get('/api/messages', headers=self.headers, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def subscribe(self, types, lead_days=3):
        response = self.client.put('/api/messages/subscription', headers=self.headers,
                                   json={'types': types, 'channel': 'site', 'lead_days': lead_days})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    # ---------------------------------------------------------------- 公告
    def test_notices_list_search_detail_and_404(self):
        self.assertEqual(self.client.get('/api/notices').status_code, 401)
        listing = self.client.get('/api/notices', headers=self.headers)
        self.assertEqual(listing.status_code, 200, listing.text)
        data = listing.json()
        self.assertEqual(data['total'], len(ANNOUNCEMENTS))
        self.assertEqual(len(data['items']), len(ANNOUNCEMENTS))
        self.assertIn('招生政策', data['categories'])
        self.assertIn('院校宣讲', data['categories'])
        self.assertEqual(set(data['items'][0]),
                         {'id', 'category', 'title', 'publish_date', 'source', 'source_url', 'summary', 'tags'})
        dates = [item['publish_date'] for item in data['items']]
        self.assertEqual(dates, sorted(dates, reverse=True))

        filtered = self.client.get('/api/notices', headers=self.headers,
                                   params={'category': '院校宣讲'}).json()
        self.assertTrue(filtered['total'] >= 1)
        self.assertTrue(all(item['category'] == '院校宣讲' for item in filtered['items']))
        self.assertEqual(filtered['categories'], data['categories'])

        searched = self.client.get('/api/notices', headers=self.headers, params={'q': '征集志愿'}).json()
        self.assertTrue(searched['total'] >= 1)
        for item in searched['items']:
            haystack = ' '.join([item['title'], item['summary'], *item['tags']])
            self.assertIn('征集志愿', haystack)

        detail = self.client.get('/api/notices/N-005', headers=self.headers)
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()['id'], 'N-005')
        self.assertIn('征集志愿', detail.json()['title'])
        self.assertEqual(self.client.get('/api/notices/N-999', headers=self.headers).status_code, 404)
        self.assertEqual(self.client.get('/api/notices', headers=self.headers, params={'limit': 0}).status_code, 422)
        self.assertEqual(self.client.get('/api/notices', headers=self.headers, params={'limit': 51}).status_code, 422)

    # ---------------------------------------------------------------- 消息列表/属主隔离
    def test_messages_owner_scoped_and_plan_submit_message(self):
        self.assertEqual(self.client.get('/api/messages').status_code, 401)
        self.assertEqual(self.client.post('/api/messages/refresh').status_code, 401)
        self.assertEqual(self.messages()['items'], [])
        self.assertEqual(self.messages()['unread'], 0)

        plan = self.save_plan('待提交方案')
        submitted = self.client.post(f"/api/plans/{plan['id']}/submit", headers=self.headers)
        self.assertEqual(submitted.status_code, 200, submitted.text)
        mine = self.messages()
        self.assertEqual(len(mine['items']), 1)
        message = mine['items'][0]
        self.assertEqual(message['type'], 'plan')
        self.assertEqual(message['title'], '志愿方案已提交')
        self.assertIn('待提交方案', message['body'])
        self.assertEqual(message['link'], '/planner')
        self.assertIsNone(message['read_at'])
        self.assertIn('created_at', message)

        # 重复提交 / 撤回后再提交：dedupe_key=plan:{id}:submit 不再重复发
        self.assertEqual(self.client.post(f"/api/plans/{plan['id']}/submit", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.post(f"/api/plans/{plan['id']}/withdraw", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.post(f"/api/plans/{plan['id']}/submit", headers=self.headers).status_code, 200)
        self.assertEqual(len(self.messages()['items']), 1)

        # 属主隔离：另一账号看不到、读不了、批量已读也影响不到
        other_user, other_headers = self.account('另一账号')
        other = self.client.get('/api/messages', headers=other_headers).json()
        self.assertEqual(other, {'unread': 0, 'items': []})
        self.assertEqual(self.client.get('/api/messages/unread-count', headers=other_headers).json(), {'unread': 0})
        self.assertEqual(self.client.post(f"/api/messages/{message['id']}/read",
                                          headers=other_headers).status_code, 404)
        self.assertEqual(self.client.post('/api/messages/read-all', headers=other_headers).json(), {'updated': 0})
        self.assertEqual(self.messages()['unread'], 1)

    # ---------------------------------------------------------------- refresh 幂等
    def test_refresh_generates_messages_and_is_idempotent(self):
        self.subscribe(['collection', 'plan', 'policy'])
        self.save_plan('未提交草稿')
        first = self.client.post('/api/messages/refresh', headers=self.headers)
        self.assertEqual(first.status_code, 200, first.text)
        body = first.json()
        self.assertGreaterEqual(body['created'], 2)  # 草稿提醒 + 最新公告
        listing = self.messages()
        types = [item['type'] for item in listing['items']]
        self.assertIn('plan', types)
        self.assertIn('policy', types)
        self.assertGreaterEqual(listing['unread'], body['created'])

        second = self.client.post('/api/messages/refresh', headers=self.headers).json()
        self.assertEqual(second['created'], 0)
        self.assertEqual(second['skipped'], body['created'])
        self.assertEqual(len(self.messages()['items']), len(listing['items']))

    def test_refresh_policy_message_tracks_latest_announcement(self):
        latest = max(ANNOUNCEMENTS, key=lambda item: (item['publish_date'], item['id']))
        self.subscribe(['policy'])
        first = self.client.post('/api/messages/refresh', headers=self.headers).json()
        self.assertEqual(first['created'], 1)
        self.assertEqual(first['skipped'], 0)
        policy = [item for item in self.messages()['items'] if item['type'] == 'policy']
        self.assertEqual(len(policy), 1)
        self.assertIn('政策公告', policy[0]['title'])
        self.assertIn(latest['title'][:12], policy[0]['title'])
        self.assertIn(latest['summary'][:16], policy[0]['body'])
        self.assertEqual(self.client.post('/api/messages/refresh', headers=self.headers).json(),
                         {'created': 0, 'skipped': 1})

    # ---------------------------------------------------------------- 已读
    def test_message_read_and_read_all(self):
        self.subscribe(['policy', 'plan'])
        self.save_plan('已读测试方案')
        created = self.client.post('/api/messages/refresh', headers=self.headers).json()['created']
        self.assertGreaterEqual(created, 2)
        unread_before = self.client.get('/api/messages/unread-count', headers=self.headers).json()['unread']
        self.assertEqual(unread_before, created)
        items = self.messages()['items']
        first_id = items[0]['id']

        read = self.client.post(f'/api/messages/{first_id}/read', headers=self.headers)
        self.assertEqual(read.status_code, 200, read.text)
        self.assertEqual(read.json(), {'read': True})
        self.assertEqual(self.client.post(f'/api/messages/{first_id}/read', headers=self.headers).json(),
                         {'read': True})  # 重复已读幂等
        self.assertEqual(self.client.get('/api/messages/unread-count', headers=self.headers).json()['unread'],
                         unread_before - 1)
        only_unread = self.messages(only_unread=True)
        self.assertNotIn(first_id, [item['id'] for item in only_unread['items']])
        marked = [item for item in self.messages()['items'] if item['id'] == first_id][0]
        self.assertIsNotNone(marked['read_at'])

        read_all = self.client.post('/api/messages/read-all', headers=self.headers)
        self.assertEqual(read_all.status_code, 200, read_all.text)
        self.assertEqual(read_all.json(), {'updated': unread_before - 1})
        self.assertEqual(self.client.get('/api/messages/unread-count', headers=self.headers).json()['unread'], 0)
        self.assertEqual(self.client.post('/api/messages/read-all', headers=self.headers).json(), {'updated': 0})
        self.assertEqual(self.messages(only_unread=True)['items'], [])
        self.assertEqual(self.client.post('/api/messages/999999/read', headers=self.headers).status_code, 404)

    # ---------------------------------------------------------------- 订阅
    def test_subscription_default_validation_and_persist(self):
        default = self.client.get('/api/messages/subscription', headers=self.headers)
        self.assertEqual(default.status_code, 200, default.text)
        self.assertEqual(default.json(), DEFAULT_SUBSCRIPTION)

        saved = self.subscribe(['policy', 'quality'], lead_days=5)
        self.assertEqual(saved, {'types': ['policy', 'quality'], 'channel': 'site', 'lead_days': 5})
        self.assertEqual(self.client.get('/api/messages/subscription', headers=self.headers).json(), saved)
        me = self.client.get('/api/auth/me', headers=self.headers).json()
        self.assertEqual(me['profile']['subscription'], saved)

        # M7-04：结果推送类型也可订阅
        self.assertEqual(self.subscribe(['result'], lead_days=1),
                         {'types': ['result'], 'channel': 'site', 'lead_days': 1})

        # 重复类型去重、缺省值补齐
        deduped = self.subscribe(['plan', 'plan', 'policy'], lead_days=0)
        self.assertEqual(deduped['types'], ['plan', 'policy'])
        self.assertEqual(deduped['lead_days'], 0)

        for bad in [{'types': ['sms']}, {'channel': 'email'}, {'lead_days': 15}, {'lead_days': -1}]:
            payload = {'types': ['plan'], 'channel': 'site', 'lead_days': 3, **bad}
            response = self.client.put('/api/messages/subscription', headers=self.headers, json=payload)
            self.assertEqual(response.status_code, 422, (bad, response.text))

        # 无画像账号：不允许保存订阅，但读取默认值可用
        _, bare_headers = self.account('无画像')
        self.assertEqual(self.client.get('/api/messages/subscription', headers=bare_headers).json(),
                         DEFAULT_SUBSCRIPTION)
        self.assertEqual(self.client.put('/api/messages/subscription', headers=bare_headers,
                                         json={'types': ['plan'], 'channel': 'site',
                                               'lead_days': 3}).status_code, 400)

    # ---------------------------------------------------------------- 征集志愿提醒（时间窗）
    def test_collection_reminder_respects_window_and_lead_days(self):
        today = date.today()

        def schedule(start_offset, end_offset, stage='征集志愿'):
            return {'provinces': {'浙江': [{'batch': '普通类第一段', 'events': [
                {'stage': stage, 'start': (today + timedelta(days=start_offset)).isoformat(),
                 'end': (today + timedelta(days=end_offset)).isoformat()},
            ]}]}}

        self.subscribe(['collection'], lead_days=3)
        with patch('app.services.notices.admission_schedule', return_value=schedule(2, 3)):
            first = self.client.post('/api/messages/refresh', headers=self.headers).json()
            self.assertEqual(first, {'created': 1, 'skipped': 0})
            collection = [item for item in self.messages()['items'] if item['type'] == 'collection']
            self.assertEqual(len(collection), 1)
            self.assertIn('征集志愿', collection[0]['title'])
            self.assertIn('距开始还有 2 天', collection[0]['body'])
            second = self.client.post('/api/messages/refresh', headers=self.headers).json()
            self.assertEqual(second, {'created': 0, 'skipped': 1})

        # 窗口在 10 天后、lead_days=3 → 不提醒
        with patch('app.services.notices.admission_schedule', return_value=schedule(10, 11)):
            self.assertEqual(self.client.post('/api/messages/refresh', headers=self.headers).json(),
                             {'created': 0, 'skipped': 0})

        # 进行中的窗口（lead_days=0 也应提醒）
        other_user, other_headers = self.account('征集测试')
        self.client.put('/api/auth/profile', headers=other_headers, json=PROFILE)
        self.client.put('/api/messages/subscription', headers=other_headers,
                        json={'types': ['collection'], 'channel': 'site', 'lead_days': 0})
        with patch('app.services.notices.admission_schedule', return_value=schedule(-1, 1)):
            ongoing = self.client.post('/api/messages/refresh', headers=other_headers).json()
            self.assertEqual(ongoing, {'created': 1, 'skipped': 0})
            item = self.client.get('/api/messages', headers=other_headers).json()['items'][0]
            self.assertIn('正在进行中', item['body'])

    # ---------------------------------------------------------------- 数据质量提醒
    def test_quality_reminder_only_when_patrol_changed(self):
        self.subscribe(['quality'])
        changed = {'last_checked_at': '2026-11-11T10:00:00+08:00', 'report_file': 'patrol_test_changed.json',
                   'items': [{'id': 'MOE-LIST', 'changed': True}, {'id': 'SD-ZK', 'changed': False}]}
        with patch('app.services.quality.latest_patrol', return_value=changed):
            first = self.client.post('/api/messages/refresh', headers=self.headers).json()
            self.assertEqual(first, {'created': 1, 'skipped': 0})
            quality = [item for item in self.messages()['items'] if item['type'] == 'quality']
            self.assertEqual(len(quality), 1)
            self.assertIn('MOE-LIST', quality[0]['body'])
            self.assertEqual(self.client.post('/api/messages/refresh', headers=self.headers).json(),
                             {'created': 0, 'skipped': 1})

        quiet = {'report_file': 'patrol_test_quiet.json', 'items': [{'id': 'MOE-LIST', 'changed': False}]}
        with patch('app.services.quality.latest_patrol', return_value=quiet):
            self.assertEqual(self.client.post('/api/messages/refresh', headers=self.headers).json(),
                             {'created': 0, 'skipped': 0})
        with patch('app.services.quality.latest_patrol', return_value=None):
            self.assertEqual(self.client.post('/api/messages/refresh', headers=self.headers).json(),
                             {'created': 0, 'skipped': 0})


if __name__ == '__main__':
    unittest.main()
