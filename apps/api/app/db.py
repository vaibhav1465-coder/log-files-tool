from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings


_settings = get_settings()
_pool = ConnectionPool(
    conninfo=_settings.database_url,
    min_size=1,
    max_size=_settings.db_pool_size,
    kwargs={"row_factory": dict_row},
    open=False,
)


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    if _pool.closed:
        _pool.open()
    with _pool.connection() as conn:
        yield conn


def initialize_database() -> None:
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    with connection() as conn:
        # API and worker may start concurrently. PostgreSQL's IF NOT EXISTS
        # does not eliminate every catalog race, so serialize migrations.
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (0x45584F53,))
        conn.execute(schema)
