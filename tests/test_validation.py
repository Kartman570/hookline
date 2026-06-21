import tempfile
import unittest
from pathlib import Path
from hookline.config import Settings
from hookline.store import Store
from hookline.signing import verify


class ValidationTests(unittest.TestCase):
    def test_bad_settings(self):
        with self.assertRaises(ValueError):
            Settings('queue.sqlite3', 'short')
        with self.assertRaises(ValueError):
            Settings('queue.sqlite3', 'access-key-long-enough', timeout=30, lease_seconds=10)

    def test_invalid_destinations(self):
        settings = Settings('queue.sqlite3', 'access-key-long-enough')
        for url in ['file:///tmp/test', 'http://user:pass@localhost/',
                    'http://localhost:bad/', 'http://localhost/with space',
                    'http://localhost/#fragment']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                settings.validate_url(url)

    def test_invalid_signature_timestamp(self):
        self.assertFalse(verify('secret', 'not-a-number', b'body', 'bad', 100))

    def test_invalid_queue_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'queue.sqlite3')
            for operation in [lambda: store.events('bad'), lambda: store.events(limit=0),
                              lambda: store.replay('missing'), lambda: store.replay('missing', 0),
                              lambda: store.set_enabled(10, False),
                              lambda: store.enqueue(10, 'key', {}),
                              lambda: store.enqueue(10, '', {})]:
                with self.assertRaises(ValueError):
                    operation()
