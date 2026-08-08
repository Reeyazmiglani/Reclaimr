"""Thin wrapper so the rest of the app can keep calling conn.execute(...)
.fetchone()/.fetchall() the way it did against sqlite3.Connection, now
backed by psycopg2. Rows behave like sqlite3.Row: row['field'], dict(row),
AND row[0] (positional, used all over the codebase for COUNT(*) etc.)
all keep working unchanged.
"""
import psycopg2
import psycopg2.extras


class _Row(psycopg2.extras.RealDictRow):
    """RealDictRow supports row['field']/dict(row) but not row[0] — add
    positional access so COUNT(*) style `.fetchone()[0]` keeps working."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _Cursor(psycopg2.extras.DictCursorBase):
    """Same as RealDictCursor, just wired to _Row instead of RealDictRow —
    RealDictCursor hardcodes its row class in __init__ rather than reading
    a class attribute, so it can't be reused by simple subclassing."""

    def __init__(self, *args, **kwargs):
        kwargs["row_factory"] = _Row
        super().__init__(*args, **kwargs)

    def execute(self, query, vars=None):
        self.column_mapping = []
        self._query_executed = True
        return super().execute(query, vars)

    def callproc(self, procname, vars=None):
        self.column_mapping = []
        self._query_executed = True
        return super().callproc(procname, vars)

    def _build_index(self):
        if self._query_executed and self.description:
            self.column_mapping = [d[0] for d in self.description]
            self._query_executed = False


class PgConnection:
    def __init__(self, dsn: str):
        self._conn = psycopg2.connect(dsn, cursor_factory=_Cursor)
        # Autocommit, matching sqlite3's behavior this codebase was written
        # against: each statement succeeds or fails independently. Without
        # this, Postgres aborts the *entire* transaction on any single
        # failed statement — and this app has many
        # `try: conn.execute(ALTER TABLE ...) except: pass` spots (expected
        # to be harmless probes under SQLite) that would otherwise poison
        # every later query on the same (st.cache_resource-cached, so
        # long-lived) connection with "current transaction is aborted".
        self._conn.autocommit = True

    def execute(self, sql, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return cur

    def executemany(self, sql, seq_of_params):
        cur = self._conn.cursor()
        cur.executemany(sql, seq_of_params)
        return cur

    def executescript(self, sql):
        cur = self._conn.cursor()
        cur.execute(sql)
        return cur

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def connect(database_url: str) -> PgConnection:
    return PgConnection(database_url)
