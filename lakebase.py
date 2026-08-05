"""
Lakebase (Databricks-managed Postgres) connection helper.

Connects using a single LAKEBASE_URL (a standard Postgres connection URL,
e.g. postgresql://role:password@host:5432/databricks_postgres?sslmode=require)
pointing at a native Postgres role with a static, non-expiring password.

This keeps setup to a single secret instead of five separate env vars.
"""

import base64
import os
from contextlib import contextmanager
from urllib.parse import urlparse

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine

_w = WorkspaceClient()

_SCOPE = os.environ.get("LAKEBASE_SECRET_SCOPE", "database")
_KEY = os.environ.get("LAKEBASE_SECRET_KEY", "lakebase-url")

# Cache so we don't hit the secrets API (and re-validate) on every call.
_cached_url: str | None = None


def _lakebase_url() -> str:
    """Fetch, decode, and validate the Lakebase connection URL from the secret scope.

    Raises a clear, actionable error immediately if the scope/key is missing,
    the value isn't valid base64/UTF-8, or the decoded URL is malformed
    (e.g. has no host, or a literal "None" host — the classic sign that the
    URL was built from an f-string before the real host value was available).
    """
    global _cached_url
    if _cached_url is not None:
        return _cached_url

    try:
        secret = _w.secrets.get_secret(scope=_SCOPE, key=_KEY)
    except Exception as e:
        raise RuntimeError(
            f"Could not read Lakebase secret '{_KEY}' from scope '{_SCOPE}'. "
            f"Check that the scope/key exist and this app's service principal "
            f"has GET permission on the scope. Original error: {e}"
        ) from e

    if not secret.value:
        raise RuntimeError(
            f"Secret '{_KEY}' in scope '{_SCOPE}' is empty. "
            f"Re-run whatever setup step writes the Lakebase connection URL."
        )

    try:
        decoded = base64.b64decode(secret.value).decode("utf-8")
    except Exception as e:
        raise RuntimeError(
            f"Secret '{_KEY}' in scope '{_SCOPE}' is not valid base64/UTF-8 "
            f"text. It should contain a base64-encoded Postgres URL. "
            f"Original error: {e}"
        ) from e

    parsed = urlparse(decoded)

    if parsed.scheme not in ("postgresql", "postgres"):
        raise RuntimeError(
            f"Lakebase URL has an unexpected scheme '{parsed.scheme}'. "
            f"Expected 'postgresql://...'. Check how the secret was generated."
        )

    if not parsed.hostname or parsed.hostname.lower() == "none":
        raise RuntimeError(
            "Lakebase URL has no valid host (host is missing or the literal "
            "string 'None'). This almost always means the URL was built with "
            "an f-string/format() call before the real Lakebase instance "
            "hostname was available (e.g. instance.read_write_dns returned "
            "None because the instance wasn't fully provisioned/started yet, "
            "or an env var used to build the string was unset). Re-generate "
            "the LAKEBASE_URL secret after confirming the instance is running "
            "and the hostname resolves, then redeploy."
        )

    if not parsed.password:
        raise RuntimeError(
            "Lakebase URL has no password. If you're using Lakebase's "
            "short-lived OAuth database credentials, that token may have "
            "expired — regenerate it rather than reusing an old static "
            "secret."
        )

    _cached_url = decoded
    return decoded


@contextmanager
def get_connection():
    """Yield a raw psycopg2 connection with a RealDictCursor factory."""
    conn = psycopg2.connect(_lakebase_url(), cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()


def get_engine():
    """Return a SQLAlchemy engine for Lakebase."""
    return create_engine(_lakebase_url())


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
