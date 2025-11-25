from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import time
import unittest
from hookline.config import Settings
from hookline.store import Store
from hookline.signing import verify
from hookline.worker import tick


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.requests = []
        requests = self.requests

        class Receiver(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                requests.append((dict(self.headers), body))
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', '/done')
                elif self.path == '/retry' and len(requests) == 1:
                    self.send_response(503)
                else:
                    self.send_response(204)
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Receiver)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(self.server.shutdown)
        self.store = Store(Path(self.temp.name) / 'queue.sqlite3')
        self.settings = Settings(self.store.path, 'local-access-key-123')

    def add_event(self, path):
        endpoint = self.store.add_endpoint('receiver',
            'http://127.0.0.1:%s%s' % (self.server.server_port, path), 'signing-secret')
        event, _ = self.store.enqueue(endpoint, 'one', {'message': 'hello'})
        return event

    def test_real_post_signature_and_retry(self):
        event = self.add_event('/retry')
        self.assertTrue(tick(self.store, self.settings, now=100))
        self.assertEqual(self.store.event(event['id'])['state'], 'pending')
        self.assertTrue(tick(self.store, self.settings, now=200))
        self.assertEqual(self.store.event(event['id'])['state'], 'delivered')
        self.assertEqual(len(self.requests), 2)
        headers, body = self.requests[0]
        self.assertTrue(verify('signing-secret', headers['X-Hookline-Timestamp'], body,
                               headers['X-Hookline-Signature'], time.time()))
        self.assertEqual(headers['X-Hookline-Id'], event['id'])

    def test_redirect_is_not_followed(self):
        event = self.add_event('/redirect')
        tick(self.store, self.settings, now=100)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.store.event(event['id'])['state'], 'dead')
