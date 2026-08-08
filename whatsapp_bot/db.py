"""Postgres connection for the WhatsApp bot service.

This service is deployed as its own Railway service (separate root
directory from the Streamlit app), so it can't `import db.connection`
across folders at runtime — this module deliberately duplicates that
wrapper's pattern (dict-like rows, forced autocommit) rather than
reaching into the main app's package. See db/connection.py in the main
app for the sibling copy this was copied from; keep them in sync if the
row-wrapping behavior ever changes.
"""
import psycopg2
import psycopg2.extras


class _Row(psycopg2.extras.RealDictRow):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _Cursor(psycopg2.extras.DictCursorBase):
    def __init__(self, *args, **kwargs):
        kwargs["row_factory"] = _Row
        super().__init__(*args, **kwargs)

    def execute(self, query, vars=None):
        self.column_mapping = []
        self._query_executed = True
        return super().execute(query, vars)

    def _build_index(self):
        if self._query_executed and self.description:
            self.column_mapping = [d[0] for d in self.description]
            self._query_executed = False


class PgConnection:
    def __init__(self, dsn: str):
        self._conn = psycopg2.connect(dsn, cursor_factory=_Cursor)
        # Autocommit, matching the main app's connection — each statement
        # succeeds or fails independently instead of poisoning a shared
        # long-lived transaction.
        self._conn.autocommit = True

    def execute(self, sql, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def connect(database_url: str) -> PgConnection:
    return PgConnection(database_url)


def ensure_whatsapp_tables(conn: PgConnection):
    """Idempotent — safe to call on every process start. The main app's
    Settings page creates/uses the same `whatsapp_numbers` table (see
    utils/auth.py there); this mirrors that DDL so the bot works even if
    it happens to boot before the web app has touched the table."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_numbers (
            id SERIAL PRIMARY KEY,
            phone_number TEXT NOT NULL UNIQUE,
            display_name TEXT,
            approved BOOLEAN NOT NULL DEFAULT FALSE,
            added_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'localtime', 'YYYY-MM-DD HH24:MI:SS')
        )
        """
    )
    # Pending write-confirmation actions, keyed by phone number, with a
    # short expiry — see tools.py's confirm-flow for how these are used.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_pending_actions (
            id SERIAL PRIMARY KEY,
            phone_number TEXT NOT NULL,
            action_type TEXT NOT NULL,
            action_payload TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            expires_at TIMESTAMP NOT NULL
        )
        """
    )
    conn.commit()
