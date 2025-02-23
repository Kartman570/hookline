import tempfile
import unittest
from pathlib import Path
from hookline.store import Store
from hookline.signing import signature, verify


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'queue.sqlite3')
        endpoint = self.store.add_endpoint('local', 'http://localhost/hook', 'secret')
        self.event, _ = self.store.enqueue(endpoint, 'key', {'message': 'hello'}, max_attempts=2)

    def test_retry_then_success(self):
        first = self.store.claim(100, 30)
        self.store.finish(first['id'], first['lease_token'], 503, None, 100, 2)
        self.assertIsNone(self.store.claim(101, 30))
        second = self.store.claim(102, 30)
        self.store.finish(second['id'], second['lease_token'], 204, None, 102, 2)
        self.assertEqual(self.store.event(second['id'])['state'], 'delivered')
        self.assertEqual(len(self.store.attempts(second['id'])), 2)

    def test_expired_worker_cannot_finish_new_claim(self):
        first = self.store.claim(100, 30)
        second = self.store.claim(131, 30)
        self.assertNotEqual(first['lease_token'], second['lease_token'])
        self.assertFalse(self.store.finish(first['id'], first['lease_token'], 200, None, 132, 0))
        self.assertIsNone(self.store.claim(162, 30))
        self.assertEqual(self.store.event(first['id'])['state'], 'dead')

    def test_permanent_failure_is_dead(self):
        event = self.store.claim(100, 30)
        self.store.finish(event['id'], event['lease_token'], 403, None, 100, 5)
        self.assertEqual(self.store.event(event['id'])['state'], 'dead')

    def test_signature_and_replay_window(self):
        body = b'{"hello":"world"}'
        signed = signature('secret', '100', body)
        self.assertTrue(verify('secret', '100', body, signed, 110))
        self.assertFalse(verify('secret', '100', b'changed', signed, 110))
        self.assertFalse(verify('secret', '100', body, signed, 500))
