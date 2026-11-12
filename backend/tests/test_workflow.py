"""Real REST workflows against a disposable SQLite database, without touching .env or local user data."""
import csv
import io
import json
import os
import secrets
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

temporary = tempfile.TemporaryDirectory(prefix='sunpath-test-')
os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(temporary.name) / 'test.db').as_posix()
os.environ['JWT_SECRET'] = secrets.token_urlsafe(48)
os.environ['DEMO_EMAIL'] = 'test-demo@sunpath.cn'
os.environ['DEMO_PASSWORD'] = 'TestOnly2026!'

from fastapi.testclient import TestClient
from app.main import app
from app.seed import seed
from app.core.database import engine, SessionLocal
from app.services.recommender import recommend, balanced_plan
from app.models.entities import Profile
from app.schemas.chat import ChatOut
from app.services.ai_matching import selection_context, validate_selection
from fastapi import HTTPException

PROFILE = {'province': '浙江', 'exam_year': 2026, 'score': 628, 'rank': 22580, 'subjects': ['物理', '化学', '生物'], 'regions': ['浙江', '江苏', '上海'], 'majors': ['计算机', '电子信息']}

class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()
        temporary.cleanup()

    def setUp(self):
        self.email = f'{secrets.token_hex(6)}@test.cn'
        response = self.client.post('/api/auth/register', json={'email': self.email, 'password': 'TestPassword123!', 'name': '测试同学'})
        self.assertEqual(response.status_code, 201, response.text)
        self.headers = {'Authorization': f"Bearer {response.json()['access_token']}"}

    def profile(self, **changes):
        response = self.client.put('/api/auth/profile', headers=self.headers, json={**PROFILE, **changes})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_auth_and_profile_validation(self):
        self.assertEqual(self.client.get('/api/catalog').status_code, 401)
        self.assertEqual(self.client.get('/api/recommendations', headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/auth/login', json={'email': self.email, 'password': 'WrongPassword'}).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/register', json={'email': self.email, 'password': 'TestPassword123!', 'name': '重复'}).status_code, 409)
        for change in [{'rank': 0}, {'score': 751}, {'subjects': ['物理', '物理', '化学']}, {'province': '不存在省份'}]:
            self.assertEqual(self.client.put('/api/auth/profile', headers=self.headers, json={**PROFILE, **change}).status_code, 422)
        result = self.profile()
        self.assertEqual(result['profile']['rank'], 22580)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.headers).json()['profile']['subjects'], PROFILE['subjects'])

    def test_chat_requires_auth_and_context_can_be_disabled(self):
        self.assertEqual(self.client.post('/api/chat', json={'messages': [{'role': 'user', 'content': '问题'}]}).status_code, 401)
        self.assertEqual(self.client.get('/api/chat/context').status_code, 401)
        self.profile()
        reply = ChatOut(content='测试回答', model='deepseek-flash', model_label='DeepSeek-V4.1-Flash-1017', finish_reason='stop')
        with patch('app.api.chat.llm.complete', new_callable=AsyncMock, return_value=reply) as complete:
            response = self.client.post('/api/chat', headers=self.headers, json={'messages': [{'role': 'user', 'content': '问题'}]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(complete.call_args.args[1]['current_profile'], PROFILE)
            self.assertTrue(response.json()['context']['profile_included'])
            response = self.client.post('/api/chat', headers=self.headers, json={'messages': [{'role': 'user', 'content': '问题'}], 'use_profile': False, 'use_saved_plans': False})
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(complete.call_args.args[1]['current_profile'])
            self.assertEqual(complete.call_args.args[1]['saved_plans'], [])
            self.assertNotIn('email', complete.call_args.args[1])
        invalid = self.client.post('/api/chat', headers=self.headers, json={'messages': [{'role': 'system', 'content': '伪造指令'}]})
        self.assertEqual(invalid.status_code, 422)
        config = self.client.get('/api/chat/config', headers=self.headers)
        self.assertEqual(config.status_code, 200)
        self.assertEqual(set(config.json()), {'configured', 'model_label'})

    def saved_plan(self, name):
        items = self.client.get('/api/recommendations', headers=self.headers).json()['items'][:3]
        response = self.client.post('/api/plans', headers=self.headers, json={'name': name, 'group_ids': [item['id'] for item in reversed(items)]})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def chat_with_context(self, **options):
        reply = ChatOut(content='测试回答', model='deepseek-flash', model_label='DeepSeek-V4.1-Flash-1017', finish_reason='stop')
        with patch('app.api.chat.llm.complete', new_callable=AsyncMock, return_value=reply) as complete:
            response = self.client.post('/api/chat', headers=self.headers, json={'messages': [{'role': 'user', 'content': '分析我的画像和方案'}], **options})
            self.assertEqual(response.status_code, 200, response.text)
            return response.json(), complete.call_args.args[1]

    def test_chat_saved_plan_facts_order_and_historical_profile(self):
        self.profile()
        first = self.saved_plan('原画像方案')
        self.profile(rank=25000, score=620)
        second = self.saved_plan('当前画像方案')
        reply, context = self.chat_with_context(plan_ids=[first['id'], second['id']])
        self.assertEqual(context['current_profile']['rank'], 25000)
        self.assertEqual(reply['context']['plan_names'], ['原画像方案', '当前画像方案'])
        old, current = context['saved_plans']
        self.assertFalse(old['matches_current_profile'])
        self.assertTrue(current['matches_current_profile'])
        self.assertEqual(old['profile_snapshot'], PROFILE)
        self.assertEqual([i['id'] for i in old['items']], [i['id'] for i in first['items']])
        self.assertEqual([i['position'] for i in old['items']], [1, 2, 3])
        for item, source in zip(old['items'], first['items']):
            self.assertEqual(item['university']['name'], source['university']['name'])
            self.assertEqual(item['latest_rank'], source['latest_rank'])
            self.assertEqual(item['risk'], source['risk'])
        self.assertEqual(sum(old['risk_counts'].values()), 3)
        serialized = json.dumps(context, ensure_ascii=False)
        for private in [self.email, '测试同学', 'TestPassword123!', 'user_id', 'access_token']:
            self.assertNotIn(private, serialized)
        _, optout = self.chat_with_context(use_profile=False)
        self.assertIsNone(optout['current_profile'])
        self.assertEqual(len(optout['saved_plans']), 2)
        self.assertIsNone(optout['saved_plans'][0]['matches_current_profile'])
        self.client.delete(f"/api/plans/{first['id']}", headers=self.headers)
        _, fresh = self.chat_with_context()
        self.assertEqual([p['plan_id'] for p in fresh['saved_plans']], [second['id']])

    def test_chat_context_is_owner_scoped_and_missing_plans_rejected(self):
        self.profile()
        own = self.saved_plan('私有方案')
        token = self.client.post('/api/auth/register', json={'email': f'{secrets.token_hex(6)}@test.cn', 'password': 'TestPassword123!', 'name': '另一账号'}).json()['access_token']
        other = {'Authorization': f'Bearer {token}'}
        listing = self.client.get('/api/chat/context', headers=other).json()
        self.assertEqual(listing['plans'], [])
        self.assertEqual(listing['saved_plan_count'], 0)
        with patch('app.api.chat.llm.complete', new_callable=AsyncMock) as complete:
            for ids in [[own['id']], [own['id'], 999999]]:
                response = self.client.post('/api/chat', headers=other, json={'messages': [{'role': 'user', 'content': '问题'}], 'plan_ids': ids})
                self.assertEqual(response.status_code, 404)
            complete.assert_not_awaited()
        available = self.client.get('/api/chat/context', headers=self.headers).json()
        self.assertEqual([p['id'] for p in available['plans']], [own['id']])

    def test_chat_context_limits_and_no_data(self):
        reply, context = self.chat_with_context()
        self.assertIsNone(context['current_profile'])
        self.assertEqual(context['saved_plans'], [])
        self.assertEqual(reply['context']['included_plan_count'], 0)
        self.profile()
        plans = [self.saved_plan(f'方案{i}') for i in range(11)]
        reply, context = self.chat_with_context()
        self.assertEqual(reply['context']['total_saved_plans'], 11)
        self.assertEqual(reply['context']['included_plan_count'], 10)
        self.assertEqual(reply['context']['omitted_plan_count'], 1)
        self.assertEqual(context['saved_plans'][0]['plan_id'], plans[-1]['id'])
        _, explicit = self.chat_with_context(plan_ids=[plans[0]['id']])
        self.assertEqual(explicit['saved_plans'][0]['plan_id'], plans[0]['id'])
        with patch('app.services.chat_context.MAX_CONTEXT_CHARS', 7000):
            reply, context = self.chat_with_context()
        self.assertLess(reply['context']['included_plan_count'], 10)
        self.assertEqual(reply['context']['omitted_plan_count'], 11 - len(context['saved_plans']))
        self.assertLessEqual(len(json.dumps(context, ensure_ascii=False)), 7000)

    def test_recommendation_eligibility_and_same_province(self):
        self.profile()
        result = self.client.get('/api/recommendations', headers=self.headers).json()
        self.assertTrue(result['items'])
        self.assertTrue(all(result['counts'][risk] > 0 for risk in ['reach', 'steady', 'safe']))
        for item in result['items']:
            self.assertEqual(item['province'], '浙江')
            self.assertTrue(set(item['required_subjects']).issubset(PROFILE['subjects']))
            self.assertGreater(item['seats'], 0)
            self.assertEqual([h['year'] for h in item['history']], [2023, 2024, 2025])
            baseline = round(sum(h['rank'] * w for h, w in zip(item['history'], [1, 2, 3])) / 6)
            self.assertEqual(item['baseline_rank'], baseline)
            ratio = PROFILE['rank'] / baseline
            self.assertEqual(item['risk'], 'safe' if ratio <= .8 else 'steady' if ratio <= 1.08 else 'reach')
        first = result['items'][0]
        self.profile(province='广东')
        changed = self.client.get('/api/catalog/' + str(first['id']), headers=self.headers, params={'province': '广东'}).json()
        self.assertNotEqual(changed['latest_rank'], first['latest_rank'])
        self.profile(subjects=['历史', '政治', '地理'])
        humanities = self.client.get('/api/recommendations', headers=self.headers).json()['items']
        self.assertTrue(humanities)
        self.assertTrue(all(not x['required_subjects'] for x in humanities))

    def test_full_plan_save_reorder_snapshot_export(self):
        self.profile()
        generated = self.client.post('/api/recommendations/generate', headers=self.headers).json()
        items = generated['items']
        self.assertEqual(len(items), 12)
        self.assertEqual(generated['missing_tiers'], [])
        ids = [x['id'] for x in reversed(items)]
        response = self.client.post('/api/plans', headers=self.headers, json={'name': '计算机优先方案', 'group_ids': ids})
        self.assertEqual(response.status_code, 201, response.text)
        plan = response.json()
        self.assertEqual([x['id'] for x in plan['items']], ids)
        plan_id = plan['id']
        response = self.client.put(f'/api/plans/{plan_id}', headers=self.headers, json={'name': '调整方案', 'group_ids': ids[1:]})
        self.assertEqual(response.status_code, 200, response.text)
        csv_response = self.client.get(f'/api/plans/{plan_id}/export', headers=self.headers)
        self.assertEqual(csv_response.status_code, 200)
        rows = list(csv.reader(io.StringIO(csv_response.content.decode('utf-8-sig'))))
        self.assertEqual(rows[0][1], '调整方案')
        self.assertEqual(len(rows) - 4, 11)
        self.assertIn('模拟数据', csv_response.text)
        self.profile(rank=50000)
        saved = self.client.get(f'/api/plans/{plan_id}', headers=self.headers).json()
        self.assertEqual(saved['profile_snapshot']['rank'], 22580)
        self.assertEqual(self.client.get('/api/plans', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.delete(f'/api/plans/{plan_id}', headers=self.headers).status_code, 204)
        self.assertEqual(self.client.get(f'/api/plans/{plan_id}', headers=self.headers).status_code, 404)

    def test_plan_ownership_and_invalid_groups(self):
        self.profile()
        ids = [x['id'] for x in self.client.post('/api/recommendations/generate', headers=self.headers).json()['items']]
        for bad in [[], [999999], [ids[0], ids[0]]]:
            self.assertIn(self.client.post('/api/plans', headers=self.headers, json={'name': '无效', 'group_ids': bad}).status_code, [400, 422])
        pid = self.client.post('/api/plans', headers=self.headers, json={'name': '私有方案', 'group_ids': ids}).json()['id']
        other = self.client.post('/api/auth/login', json={'email': 'test-demo@sunpath.cn', 'password': 'TestOnly2026!'}).json()['access_token']
        other_headers = {'Authorization': f'Bearer {other}'}
        for method, path in [('get', f'/api/plans/{pid}'), ('get', f'/api/plans/{pid}/export'), ('delete', f'/api/plans/{pid}')]:
            self.assertEqual(getattr(self.client, method)(path, headers=other_headers).status_code, 404)
        self.assertEqual(self.client.put(f'/api/plans/{pid}', headers=other_headers, json={'name': '篡改', 'group_ids': ids}).status_code, 404)

    def test_logout_revokes_token_and_password_revokes_sessions(self):
        self.assertEqual(self.client.post('/api/auth/logout', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.headers).status_code, 401)
        token = self.client.post('/api/auth/login', json={'email': self.email, 'password': 'TestPassword123!'}).json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        self.assertEqual(self.client.put('/api/auth/password', headers=headers, json={'current_password': 'TestPassword123!', 'new_password': 'ChangedPassword123!'}).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me', headers=headers).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login', json={'email': self.email, 'password': 'ChangedPassword123!'}).status_code, 200)

    def test_catalog_filters_pagination_missing_year(self):
        response = self.client.get('/api/catalog', headers=self.headers, params={'q': '计算机', 'region': '浙江', 'page_size': 2}).json()
        self.assertEqual(len(response['items']), 2)
        self.assertTrue(all(x['university']['region'] == '浙江' and '计算机' in ' '.join(x['majors']) for x in response['items']))
        next_page = self.client.get('/api/catalog', headers=self.headers, params={'q': '计算机', 'region': '浙江', 'page_size': 2, 'page': 2}).json()
        self.assertNotEqual(response['items'][0]['id'], next_page['items'][0]['id'])
        self.assertEqual(self.client.get('/api/catalog', headers=self.headers, params={'province': '无效'}).status_code, 422)
        self.profile(exam_year=2027)
        self.assertEqual(self.client.get('/api/recommendations', headers=self.headers).json()['items'], [])
        generated = self.client.post('/api/recommendations/generate', headers=self.headers).json()
        self.assertEqual(generated['items'], [])
        self.assertEqual(len(generated['missing_tiers']), 3)

    def test_rule_boundaries_and_seed_idempotency(self):
        with SessionLocal() as db:
            for rank in [1, 2000000]:
                p = Profile(**{**PROFILE, 'rank': rank})
                result = recommend(db, p)
                if rank == 1:
                    self.assertTrue(result)
                    self.assertTrue(all(x['risk'] == 'safe' for x in result))
                else:
                    self.assertEqual(result, [])
                selected, missing = balanced_plan(result, 12)
                self.assertEqual(len({x['id'] for x in selected}), len(selected))
                self.assertIn('reach', missing)
        before = self.client.get('/api/overview', headers=self.headers).json()
        seed()
        after = self.client.get('/api/overview', headers=self.headers).json()
        self.assertEqual(before, after)
        self.assertEqual(after['groups'], 120)
        self.assertEqual(after['universities'], 60)

    def test_catalog_map_covers_all_filtered_schools_without_pagination_loss(self):
        self.assertEqual(self.client.get('/api/catalog').status_code, 401)
        first = self.client.get('/api/catalog', headers=self.headers, params={'page_size': 2}).json()
        self.assertEqual(len(first['items']), 2)
        self.assertEqual(len(first['universities']), 60)
        self.assertEqual(sum(s['group_count'] for s in first['universities']), first['total'])
        self.assertEqual(len({s['id'] for s in first['universities']}), 60)
        for school in first['universities']:
            location = school['location']
            self.assertTrue(18 < location['latitude'] < 54)
            self.assertTrue(73 < location['longitude'] < 136)
            self.assertTrue(location['source_url'].startswith('https://www.wikidata.org/'))
            self.assertEqual(school['group_count'], len(school['group_ids']))
        donghua = next(s for s in first['universities'] if s['name'] == '东华大学')
        self.assertTrue(30 < donghua['location']['latitude'] < 32)
        self.assertIn('Q837544', donghua['location']['source_url'])
        self.assertEqual(sum(s['location']['precision'] == 'city' for s in first['universities']), 2)
        filtered = self.client.get('/api/catalog', headers=self.headers, params={'q': '计算机', 'region': '浙江', 'subject': '物理', 'page_size': 1}).json()
        self.assertTrue(filtered['universities'])
        self.assertTrue(all(s['region'] == '浙江' for s in filtered['universities']))
        self.assertEqual(sum(s['group_count'] for s in filtered['universities']), filtered['total'])
        missing = self.client.get('/api/catalog', headers=self.headers, params={'q': '没有这所大学'}).json()
        self.assertEqual(missing['universities'], [])
        from app.services.geography import university_locations
        original = first['items'][0]
        unknown = {**original, 'university': {**original['university'], 'name': '新增待定位学校'}}
        self.assertIsNone(university_locations([unknown])[0]['location'])

    def mock_ai_selection(self, skill, context):
        self.assertIn('JSON', skill)
        # 上下文只携带可选的组；不可选的组以 ID 列表给出，避免给小上下文模型塞十几万字符
        self.assertEqual(len(context['catalog']), len(context['eligible_group_ids']))
        self.assertGreaterEqual(len({g['university_id'] for g in context['catalog']}), 1)
        self.assertGreaterEqual(len(context['ineligible_group_ids']), 0)
        self.assertNotIn('email', context['candidate_profile'])
        self.assertNotIn('name', context['candidate_profile'])
        selected = []
        for risk, count in context['risk_quotas'].items():
            candidates = [g['group_id'] for g in reversed(context['catalog']) if g['risk'] == risk]
            selected.extend(candidates[:count])
        self.expected_ai_ids = selected
        result = ChatOut(content='{}', model='deepseek-flash', model_label='DeepSeek-V4.1-Flash-1017', finish_reason='stop')
        return {'group_ids': selected}, result

    def test_ai_matching_selects_ids_and_rebuilds_facts(self):
        self.profile()
        original = {g['id']: g for g in self.client.get('/api/recommendations', headers=self.headers).json()['items']}
        with patch('app.services.ai_matching.llm.complete_json', new_callable=AsyncMock, side_effect=self.mock_ai_selection) as ai:
            response = self.client.post('/api/recommendations/ai', headers=self.headers, json={'count': 12})
            self.assertEqual(response.status_code, 200, response.text)
            ai.assert_awaited_once()
        data = response.json()
        self.assertEqual([g['id'] for g in data['items']], self.expected_ai_ids)
        self.assertEqual(len(data['items']), 12)
        self.assertGreaterEqual(data['ai_selection']['catalog_universities'], 1)
        for item in data['items']:
            self.assertEqual(item, original[item['id']])
            self.assertEqual(item['history_rank_min'], min(h['rank'] for h in item['history']))
            self.assertEqual(item['history_rank_max'], max(h['rank'] for h in item['history']))
        saved = self.client.post('/api/plans', headers=self.headers, json={'name': 'AI 精选方案', 'group_ids': self.expected_ai_ids})
        self.assertEqual(saved.status_code, 201)
        self.assertEqual([g['id'] for g in saved.json()['items']], self.expected_ai_ids)

    def test_ai_matching_count_limits_and_auth(self):
        self.assertEqual(self.client.post('/api/recommendations/ai', json={'count': 12}).status_code, 401)
        self.profile()
        with patch('app.services.ai_matching.llm.complete_json', new_callable=AsyncMock, side_effect=self.mock_ai_selection) as ai:
            for count in [0, 2, 31, True, 3.5, '12']:
                response = self.client.post('/api/recommendations/ai', headers=self.headers, json={'count': count})
                self.assertEqual(response.status_code, 422)
            self.assertEqual(self.client.post('/api/recommendations/ai', headers=self.headers, json={'count': 12, 'model': 'override'}).status_code, 422)
            ai.assert_not_awaited()
            for count in [3, 30]:
                response = self.client.post('/api/recommendations/ai', headers=self.headers, json={'count': count})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(len(response.json()['items']), count)
                if count == 3:
                    self.assertEqual(response.json()['counts'], {'reach': 1, 'steady': 1, 'safe': 1})

    def test_ai_matching_rejects_unknown_duplicates_and_changed_facts(self):
        with SessionLocal() as db:
            context, by_id = selection_context(db, Profile(**PROFILE), 12)
        selected, _ = balanced_plan(list(by_id.values()), 12)
        ids = [g['id'] for g in selected]
        invalid = context['ineligible_group_ids'][0]
        cases = [
            {'group_ids': ids[:-1]},
            {'group_ids': [*ids[:-1], ids[0]]},
            {'group_ids': [*ids[:-1], 999999]},
            {'group_ids': [*ids[:-1], invalid]},
            {'group_ids': ids, 'university': '虚构大学'},
            {'group_ids': ids, 'min_score': 999},
            {'group_ids': [str(i) for i in ids]},
            {'group_ids': [True, *ids[1:]]},
            {'group_ids': [g['id'] for g in by_id.values() if g['risk'] == 'safe'][:12]},
        ]
        for raw in cases:
            with self.assertRaises(HTTPException) as raised:
                validate_selection(raw, context, by_id)
            self.assertEqual(raised.exception.status_code, 502)

    def test_ai_matching_no_candidates_never_calls_model(self):
        self.profile(exam_year=2027)
        with patch('app.services.ai_matching.llm.complete_json', new_callable=AsyncMock) as ai:
            response = self.client.post('/api/recommendations/ai', headers=self.headers, json={'count': 12})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['items'], [])
            self.assertTrue(response.json()['ai_selection']['below_minimum'])
            self.assertIsNone(response.json()['ai_selection']['model_label'])
            ai.assert_not_awaited()

    def test_ai_matching_insufficient_candidates_and_bad_profile(self):
        with SessionLocal() as db:
            context, by_id = selection_context(db, Profile(**PROFILE), 12)
            for values in [{**PROFILE, 'rank': 0}, {**PROFILE, 'score': 751}]:
                with self.assertRaises(HTTPException) as raised:
                    selection_context(db, Profile(**values), 12)
                self.assertEqual(raised.exception.status_code, 400)
        self.profile()
        available = list(by_id.values())[:2]
        with patch('app.services.ai_matching.recommend', return_value=available), patch('app.services.ai_matching.llm.complete_json', new_callable=AsyncMock, side_effect=self.mock_ai_selection):
            response = self.client.post('/api/recommendations/ai', headers=self.headers, json={'count': 12})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(len(response.json()['items']), 2)
            self.assertTrue(response.json()['ai_selection']['below_minimum'])

    def test_ai_matching_provider_error_is_not_silently_replaced(self):
        self.profile()
        with patch('app.services.ai_matching.llm.complete_json', new_callable=AsyncMock, side_effect=HTTPException(502, '模型服务失败')):
            response = self.client.post('/api/recommendations/ai', headers=self.headers, json={'count': 12})
            self.assertEqual(response.status_code, 502)
            self.assertNotIn('items', response.json())

    def test_ai_matching_one_correction_is_bounded_and_verified(self):
        self.profile()
        seen = []
        async def repair(skill, context):
            output, result = self.mock_ai_selection(skill, context)
            seen.append('validation_feedback' in context)
            if len(seen) == 1:
                used = set(output['group_ids'])
                spare = next(i for i in context['eligible_buckets']['safe']['allowed_ids'] if i not in used)
                output['group_ids'][0] = spare
            return output, result
        with patch('app.services.ai_matching.llm.complete_json', new_callable=AsyncMock, side_effect=repair) as ai:
            response = self.client.post('/api/recommendations/ai', headers=self.headers, json={'count': 12})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['ai_selection']['attempts'], 2)
            self.assertEqual(ai.await_count, 2)
            self.assertEqual(seen, [False, True])
            self.assertEqual(response.json()['counts'], {'reach': 3, 'steady': 6, 'safe': 3})
        result = ChatOut(content='{}', model='deepseek-flash', model_label='DeepSeek-V4.1-Flash-1017', finish_reason='stop')
        with patch('app.services.ai_matching.llm.complete_json', new_callable=AsyncMock, return_value=({'group_ids': [999999]}, result)) as ai:
            response = self.client.post('/api/recommendations/ai', headers=self.headers, json={'count': 12})
            self.assertEqual(response.status_code, 502)
            self.assertEqual(ai.await_count, 2)

if __name__ == '__main__':
    unittest.main()
