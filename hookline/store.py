import sqlite3
from contextlib import contextmanager


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS endpoints (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL,
                    secret TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY, endpoint_id INTEGER NOT NULL REFERENCES endpoints(id),
                    dedupe_key TEXT NOT NULL, payload TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 5, next_at REAL NOT NULL DEFAULT 0,
                    lease_until REAL, lease_token TEXT,
                    UNIQUE(endpoint_id, dedupe_key)
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id),
                    number INTEGER NOT NULL, token TEXT NOT NULL UNIQUE,
                    result TEXT NOT NULL, status_code INTEGER, error TEXT,
                    UNIQUE(event_id, number)
                );
                CREATE INDEX IF NOT EXISTS events_due ON events(state, next_at);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        try:
            yield db
        finally:
            db.close()

    def add_endpoint(self, name, url, secret):
        with self.connection() as db:
            cursor = db.execute('INSERT INTO endpoints(name, url, secret) VALUES (?, ?, ?)',
                                (name, url, secret))
            return cursor.lastrowid

    def endpoints(self):
        with self.connection() as db:
            return [dict(row) for row in db.execute(
                'SELECT id, name, url, enabled FROM endpoints ORDER BY id')]

    def endpoint(self, endpoint_id):
        with self.connection() as db:
            row = db.execute('SELECT * FROM endpoints WHERE id=?', (endpoint_id,)).fetchone()
            return dict(row) if row else None

    def enqueue(self, endpoint_id, key, payload, max_attempts=5):
        import json
        import uuid
        if not key or len(key) > 200 or not 1 <= max_attempts <= 20:
            raise ValueError('Invalid idempotency key or attempt limit')
        body = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if len(body.encode()) > 65536:
            raise ValueError('Payload exceeds 64 KiB')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            endpoint = db.execute('SELECT * FROM endpoints WHERE id=?', (endpoint_id,)).fetchone()
            if not endpoint or not endpoint['enabled']:
                raise ValueError('Endpoint is missing or disabled')
            existing = db.execute('SELECT * FROM events WHERE endpoint_id=? AND dedupe_key=?',
                                  (endpoint_id, key)).fetchone()
            if existing:
                if existing['payload'] != body:
                    raise ValueError('Idempotency key already has a different payload')
                db.commit()
                return dict(existing), False
            event_id = uuid.uuid4().hex
            db.execute("""INSERT INTO events(id, endpoint_id, dedupe_key, payload, max_attempts)
                VALUES (?, ?, ?, ?, ?)""", (event_id, endpoint_id, key, body, max_attempts))
            result = dict(db.execute('SELECT * FROM events WHERE id=?', (event_id,)).fetchone())
            db.commit()
            return result, True

    def event(self, event_id):
        with self.connection() as db:
            row = db.execute('SELECT * FROM events WHERE id=?', (event_id,)).fetchone()
            return dict(row) if row else None

    def claim(self, now, lease_seconds):
        import uuid
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            expired = db.execute("SELECT * FROM events WHERE state='processing' AND lease_until<=?",
                                 (now,)).fetchall()
            for event in expired:
                db.execute("UPDATE attempts SET result='expired', error='LeaseExpired' WHERE token=?",
                           (event['lease_token'],))
                state = 'dead' if event['attempts'] >= event['max_attempts'] else 'pending'
                db.execute("""UPDATE events SET state=?, lease_token=NULL, lease_until=NULL,
                           next_at=? WHERE id=?""", (state, now, event['id']))
            event = db.execute("""SELECT e.* FROM events e JOIN endpoints p ON p.id=e.endpoint_id
                WHERE e.state='pending' AND e.next_at<=? AND p.enabled=1
                ORDER BY e.next_at, e.rowid LIMIT 1""", (now,)).fetchone()
            if not event:
                db.commit()
                return None
            token = uuid.uuid4().hex
            number = event['attempts'] + 1
            db.execute("""UPDATE events SET state='processing', attempts=?, lease_until=?,
                lease_token=? WHERE id=?""", (number, now + lease_seconds, token, event['id']))
            db.execute('INSERT INTO attempts(event_id, number, token, result) VALUES (?, ?, ?, ?)',
                       (event['id'], number, token, 'processing'))
            result = dict(db.execute('SELECT * FROM events WHERE id=?', (event['id'],)).fetchone())
            db.commit()
            return result

    def finish(self, event_id, token, status_code, error, now, delay):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            event = db.execute("SELECT * FROM events WHERE id=? AND state='processing' "
                               'AND lease_token=?', (event_id, token)).fetchone()
            if not event:
                db.commit()
                return False
            if status_code is not None and 200 <= status_code < 300:
                state = 'delivered'
            elif (status_code is None or status_code in {408, 429} or status_code >= 500) and (
                    event['attempts'] < event['max_attempts']):
                state = 'pending'
            else:
                state = 'dead'
            db.execute('UPDATE attempts SET result=?, status_code=?, error=? WHERE token=?',
                       (state, status_code, error, token))
            db.execute("""UPDATE events SET state=?, next_at=?, lease_until=NULL, lease_token=NULL
                WHERE id=?""", (state, now + delay, event_id))
            db.commit()
            return True

    def attempts(self, event_id):
        with self.connection() as db:
            return [dict(row) for row in db.execute(
                'SELECT number, result, status_code, error FROM attempts WHERE event_id=? '
                'ORDER BY number', (event_id,))]
