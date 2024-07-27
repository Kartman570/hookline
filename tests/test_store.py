import tempfile
import unittest
from pathlib import Path
from hookline.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'test.sqlite3')
        self.endpoint = self.store.add_endpoint('test', 'http://localhost/hook', 'test-secret')

    def test_idempotency(self):
        first, created = self.store.enqueue(self.endpoint, 'key', {'hello': 'world'})
        second, repeated = self.store.enqueue(self.endpoint, 'key', {'hello': 'world'})
        self.assertTrue(created)
        self.assertFalse(repeated)
        self.assertEqual(first['id'], second['id'])
        with self.assertRaises(ValueError):
            self.store.enqueue(self.endpoint, 'key', {'other': 'value'})

    def test_persistence_and_secret_omission(self):
        event, _ = self.store.enqueue(self.endpoint, 'key', {'a': 1})
        reopened = Store(self.store.path)
        self.assertEqual(reopened.event(event['id'])['payload'], '{"a":1}')
        self.assertNotIn('secret', reopened.endpoints()[0])

    def test_payload_limit(self):
        with self.assertRaises(ValueError):
            self.store.enqueue(self.endpoint, 'large', {'text': 'x' * 65536})
