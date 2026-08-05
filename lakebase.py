%pip install sqlalchemy

"""
Lakebase (Databricks-managed Postgres) connection helper.

Instead of storing a pre-built, static connection URL in a secret (which goes
stale the moment the instance hostname changes or the credential expires),
this fetches the instance's real hostname and generates a fresh short-lived
OAuth database credential on demand, then builds the connection from those
live values.

Required environment variables (set these in app.yaml / the app's env config):
    LAKEBASE_INSTANCE_NAME   - name of the Lakebase database instance
    LAKEBASE_PG_ROLE         - Postgres role/user to connect as

Optional:
    LAKEBASE_DATABASE        - database name (default: "databricks_postgres")

The app's service principal must have permission to read the instance and to
generate database credentials for LAKEBASE_PG_ROLE.
"""

import datetime
import os
import time
import uuid
from contextlib import contextmanager

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine

_w = WorkspaceClient()

_INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE_NAME")
_DATABASE = os.environ.get("LAKEBASE_DATABASE", "databricks_postgres")
_PG_ROLE = os.environ.get("LAKEBASE_PG_ROLE")

# Refresh the OAuth credential this many seconds before it actually expires,
# so we never hand out a token that's about to die mid-query.
_REFRESH_BUFFER_SECONDS = 300
# Databricks credentials are typically valid ~1 hour; used only as a fallback
# if the SDK response doesn't include an explicit expiry.
_DEFAULT_TOKEN_TTL_SECONDS = 3600

_cached_host: str | None = None
_cached_token: str | None = None
_cached_expiry: float = 0.0


def _require_config():
    missing = [
        name
        for name, val in [
            ("LAKEBASE_INSTANCE_NAME", _INSTANCE_NAME),
            ("LAKEBASE_PG_ROLE", _PG_ROLE),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(
            f"Missing required env var(s) for Lakebase: {', '.join(missing)}. "
            f"Set these in the app's environment configuration."
        )


def _get_host() -> str:
    """Fetch (and cache) the instance's real read/write DNS hostname."""
    global _cached_host
    if _cached_host:
        return _cached_host

    _require_config()
    instance = _w.database.get_database_instance(name=_INSTANCE_NAME)
    host = getattr(instance, "read_write_dns", None)
    if not host:
        raise RuntimeError(
            f"Lakebase instance '{_INSTANCE_NAME}' has no read_write_dns yet. "
            f"Current state: {getattr(instance, 'state', 'unknown')}. "
            f"It may still be starting — check the instance status in the "
            f"Databricks UI before retrying."
        )
    _cached_host = host
    return host


def _get_credential() -> str:
    """Return a valid OAuth database credential, generating a fresh one if the
    cached one is missing or close to expiry."""
    global _cached_token, _cached_expiry

    now = time.time()
    if _cached_token and now < _cached_expiry - _REFRESH_BUFFER_SECONDS:
        return _cached_token

    _require_config()
    cred = _w.database.generate_database_credential(
        request_id=str(uuid.uuid4()),
        instance_names=[_INSTANCE_NAME],
    )
    if not cred.token:
        raise RuntimeError(
            "generate_database_credential() returned no token. Check that "
            "this app's service principal has permission to generate "
            f"credentials for instance '{_INSTANCE_NAME}'."
        )

    expiry_raw = getattr(cred, "expiration_time", None)
    if expiry_raw is not None:
        try:
            _cached_expiry = expiry_raw.timestamp()
        except AttributeError:
            _cached_expiry = datetime.datetime.fromisoformat(str(expiry_raw)).timestamp()
    else:
        _cached_expiry = now + _DEFAULT_TOKEN_TTL_SECONDS

    _cached_token = cred.token
    return _cached_token


def _connection_kwargs() -> dict:
    """Build fresh psycopg2 connection kwargs using the current host + credential."""
    return {
        "host": _get_host(),
        "port": 5432,
        "dbname": _DATABASE,
        "user": _PG_ROLE,
        "password": _get_credential(),
        "sslmode": "require",
    }


@contextmanager
def get_connection():
    """Yield a raw psycopg2 connection with a RealDictCursor factory, using a
    freshly-validated host and credential."""
    conn = psycopg2.connect(cursor_factory=RealDictCursor, **_connection_kwargs())
    try:
        yield conn
    finally:
        conn.close()


def _engine_creator():
    """Creator function so every new pooled connection picks up a fresh,
    still-valid credential automatically instead of a baked-in URL."""
    return psycopg2.connect(**_connection_kwargs())


def get_engine():
    """Return a SQLAlchemy engine for Lakebase.

    Uses a creator function rather than a static URL so new connections
    always pick up a valid credential. pool_recycle forces existing pooled
    connections to be replaced every 30 minutes, well under the ~1hr token
    lifetime, so long-running processes never hold an expired connection.
    """
    return create_engine(
        "postgresql://",
        creator=_engine_creator,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def run_query(sql: str, params: tuple | dict | None = None) -> list[dict]:
    """Run a read query against Lakebase and return rows as list[dict]."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def run_write(sql: str, params: tuple | dict | None = None) -> int:
    """Run an INSERT/UPDATE/DELETE against Lakebase, return affected row count."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount