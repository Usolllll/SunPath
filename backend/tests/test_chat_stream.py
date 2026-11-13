# -*- coding: utf-8 -*-
"""AI 问答流式接口（SSE）测试；上游模型全部 mock，不产生真实网络调用。"""
import json
import secrets
import unittest
from unittest.mock import patch

try:
    import test_workflow  # noqa: F401  先设置临时 DATABASE_URL
except ImportError:
    from tests import test_workflow  # noqa: F401

from fastapi.testclient import TestClient

from app.core.database import engine
from app.main import app
from app.seed import seed


def parse_sse(text: str):
    events = []
    for block in text.split('\n\n'):
        block = block.strip()
        if not block:
            continue
        event, data = 'message', ''
        for line in block.split('\n'):
            if line.startswith('event:'):
                event = line[6:].strip()
            elif line.startswith('data:'):
                data += line[5:].strip()
        if data:
            events.append((event, json.loads(data)))
    return events


class ChatStreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()

    def setUp(self):
        email = f'{secrets.token_hex(6)}@stream-test.cn'
        response = self.client.post('/api/auth/register',
                                    json={'email': email, 'password': 'StreamTest123!', 'name': '流式测试'})
        self.assertEqual(response.status_code, 201, response.text)
        self.headers = {'Authorization': f"Bearer {response.json()['access_token']}"}

    def test_stream_requires_auth(self):
        response = self.client.post('/api/chat/stream',
                                    json={'messages': [{'role': 'user', 'content': '你好'}]})
        self.assertEqual(response.status_code, 401, response.text)

    def test_stream_yields_meta_deltas_and_done(self):
        async def fake_stream(messages, context=None):
            self.assertEqual(messages[-1].content, '平行志愿是什么？')
            yield {'type': 'delta', 'content': '平行志愿是'}
            yield {'type': 'delta', 'content': '按位次依次投档。'}
            yield {'type': 'done', 'model': 'test-model', 'model_label': '测试模型', 'finish_reason': 'stop'}

        with patch('app.api.chat.llm.stream', fake_stream):
            response = self.client.post(
                '/api/chat/stream', headers=self.headers,
                json={'messages': [{'role': 'user', 'content': '平行志愿是什么？'}],
                      'use_profile': True, 'use_saved_plans': False},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('text/event-stream', response.headers['content-type'])
        events = parse_sse(response.text)
        self.assertEqual([event for event, _ in events], ['meta', 'delta', 'delta', 'done'])
        self.assertTrue(events[0][1]['model_label'])
        self.assertIn('context', events[0][1])
        content = ''.join(payload['content'] for event, payload in events if event == 'delta')
        self.assertEqual(content, '平行志愿是按位次依次投档。')
        done = events[-1][1]
        self.assertEqual(done['finish_reason'], 'stop')
        self.assertEqual(done['model'], 'test-model')
        self.assertEqual(done['model_label'], '测试模型')
        self.assertIn('context', done)

    def test_stream_provider_error_becomes_error_event(self):
        async def fake_stream(messages, context=None):
            yield {'type': 'error', 'detail': '模型服务额度不足或免费通道限速，请稍后重试', 'status': 503}

        with patch('app.api.chat.llm.stream', fake_stream):
            response = self.client.post(
                '/api/chat/stream', headers=self.headers,
                json={'messages': [{'role': 'user', 'content': '你好'}],
                      'use_profile': False, 'use_saved_plans': False},
            )
        self.assertEqual(response.status_code, 200, response.text)
        events = parse_sse(response.text)
        self.assertEqual([event for event, _ in events], ['meta', 'error'])
        self.assertEqual(events[-1][1]['status'], 503)
        self.assertIn('限速', events[-1][1]['detail'])
        self.assertIn('context', events[-1][1])

    def test_stream_keeps_conversation_validation(self):
        response = self.client.post(
            '/api/chat/stream', headers=self.headers,
            json={'messages': [{'role': 'assistant', 'content': '先说话'}]},
        )
        self.assertEqual(response.status_code, 422, response.text)


if __name__ == '__main__':
    unittest.main()
