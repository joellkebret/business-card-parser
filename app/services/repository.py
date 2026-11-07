"""Transactional SQLite persistence of canonical vCard content."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

from app.core.errors import ServiceError


class CardRepository:
    def __init__(self, database_url: str):
        if not database_url.startswith('sqlite:///') or database_url == 'sqlite:///:memory:':
            raise ValueError('DATABASE_URL must be sqlite:///path or disabled')
        self.path = Path(database_url.removeprefix('sqlite:///'))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS cards (
                id TEXT PRIMARY KEY, vcard TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def create(self, vcard):
        identifier, now = str(uuid4()), self._now()
        with self.connection() as db:
            db.execute('INSERT INTO cards VALUES (?, ?, ?, ?)', (identifier, vcard, now, now))
        return dict(id=identifier, vcard=vcard, created_at=now, updated_at=now)

    def get(self, identifier):
        with self.connection() as db:
            row = db.execute('SELECT * FROM cards WHERE id = ?', (identifier,)).fetchone()
        if row is None:
            raise ServiceError('not_found', 'Card not found.', 404)
        return dict(row)

    def list(self, limit, offset):
        with self.connection() as db:
            return [dict(row) for row in db.execute('SELECT * FROM cards ORDER BY created_at, id LIMIT ? OFFSET ?', (limit, offset))]

    def update(self, identifier, vcard):
        now = self._now()
        with self.connection() as db:
            result = db.execute('UPDATE cards SET vcard = ?, updated_at = ? WHERE id = ?', (vcard, now, identifier))
            if not result.rowcount:
                raise ServiceError('not_found', 'Card not found.', 404)
            row = db.execute('SELECT * FROM cards WHERE id = ?', (identifier,)).fetchone()
        return dict(row)

    def delete(self, identifier):
        with self.connection() as db:
            if not db.execute('DELETE FROM cards WHERE id = ?', (identifier,)).rowcount:
                raise ServiceError('not_found', 'Card not found.', 404)
