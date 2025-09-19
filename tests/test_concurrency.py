from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from hookline.store import Store


class ConcurrencyTests(unittest.TestCase):
    def test_competing_workers_claim_once(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'queue.sqlite3')
            endpoint = store.add_endpoint('test', 'http://localhost/hook', 'secret')
            for index in range(12):
                store.enqueue(endpoint, str(index), {'index': index})
            with ThreadPoolExecutor(max_workers=6) as pool:
                claims = list(pool.map(lambda _: store.claim(100, 30), range(18)))
            ids = [claim['id'] for claim in claims if claim]
            self.assertEqual(len(ids), 12)
            self.assertEqual(len(set(ids)), 12)
            self.assertEqual(store.stats()['processing'], 12)

    def test_duplicate_enqueues_share_one_event(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'queue.sqlite3')
            endpoint = store.add_endpoint('test', 'http://localhost/hook', 'secret')
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(lambda _: store.enqueue(endpoint, 'one', {'value': 1}),
                                        range(12)))
            self.assertEqual(sum(created for _, created in results), 1)
            self.assertEqual(len({event['id'] for event, _ in results}), 1)
