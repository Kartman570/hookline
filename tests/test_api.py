import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from hookline.api import create_app
from hookline.config import Settings


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings = Settings(str(Path(self.temp.name) / 'api.sqlite3'), 'test-access-key-123')
        self.app = create_app(settings)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.headers = {'Authorization': 'Bearer test-access-key-123'}

    def endpoint(self):
        result = self.client.post('/endpoints', headers=self.headers, json={
            'name': 'receiver', 'url': 'http://localhost/hook', 'secret': 'signing-test-key-123'})
        self.assertEqual(result.status_code, 201)
        return result.json()['id']

    def test_authentication_and_secret_omission(self):
        self.assertEqual(self.client.get('/endpoints').status_code, 401)
        self.endpoint()
        data = self.client.get('/endpoints', headers=self.headers).json()
        self.assertNotIn('secret', data[0])

    def test_enqueue_inspect_and_pause(self):
        endpoint = self.endpoint()
        body = {'endpoint_id': endpoint, 'key': 'one', 'payload': {'count': 3}}
        created = self.client.post('/events', headers=self.headers, json=body)
        self.assertEqual(created.status_code, 202)
        event_id = created.json()['id']
        repeated = self.client.post('/events', headers=self.headers, json=body)
        self.assertFalse(repeated.json()['created'])
        body['payload'] = {'count': 4}
        self.assertEqual(self.client.post('/events', headers=self.headers, json=body).status_code, 409)
        self.assertEqual(self.client.get('/events/' + event_id, headers=self.headers).status_code, 200)
        self.client.patch('/endpoints/%s?enabled=false' % endpoint, headers=self.headers)
        self.assertIsNone(self.app.state.store.claim(100, 30))
        self.assertEqual(len(self.client.get('/events?state=pending', headers=self.headers).json()), 1)

    def test_reject_unknown_host_and_invalid_page(self):
        response = self.client.post('/endpoints', headers=self.headers, json={
            'name': 'bad', 'url': 'http://example.com/hook', 'secret': 'test-signing-secret'})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get('/events?limit=1000', headers=self.headers).status_code, 422)

    def test_replay_preserves_previous_attempts(self):
        store = self.app.state.store
        endpoint = self.endpoint()
        event, _ = store.enqueue(endpoint, 'one', {'test': True})
        claimed = store.claim(100, 30)
        store.finish(event['id'], claimed['lease_token'], 400, None, 100, 0)
        response = self.client.post('/events/' + event['id'] + '/replay', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        second = store.claim(200, 30)
        self.assertEqual(second['attempts'], 2)
        store.finish(event['id'], second['lease_token'], 204, None, 200, 0)
        attempts = self.client.get('/events/' + event['id'] + '/attempts', headers=self.headers).json()
        self.assertEqual([row['result'] for row in attempts], ['dead', 'delivered'])
