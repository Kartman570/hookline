import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import time
from hookline.signing import verify


def main():
    parser = argparse.ArgumentParser(description='Receive signed local test events')
    parser.add_argument('--port', type=int, default=8090)
    args = parser.parse_args()
    secret = os.environ['RECEIVER_SECRET']

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                length = -1
            if not 0 <= length <= 65536:
                self.send_error(413)
                return
            body = self.rfile.read(length)
            valid = verify(secret, self.headers.get('X-Hookline-Timestamp', ''), body,
                           self.headers.get('X-Hookline-Signature', ''), time.time())
            if not valid:
                self.send_error(401)
                return
            try:
                payload = json.loads(body)
            except ValueError:
                self.send_error(400)
                return
            print(json.dumps({'id': self.headers.get('X-Hookline-Id'), 'payload': payload}),
                  flush=True)
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Receiver)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
