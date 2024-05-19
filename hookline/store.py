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
