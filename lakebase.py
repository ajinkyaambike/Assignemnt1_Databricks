"""
Lakebase Postgres (Autoscaling) connection helper.

IMPORTANT: this project uses Lakebase Autoscaling (projects/branches/endpoints),
not the older Lakebase Provisioned model. Credential generation therefore uses
the `w.postgres` SDK namespace, NOT `w.database` (that namespace is for
Provisioned instances and will 404 for an Autoscaling endpoint).

Required environment variables (set these in app.yaml — see below):
    PGHOST         - endpoint hostname, e.g. ep-xxxx.database.<region>.databricks.com
    PGDATABASE     - database name, usually "databricks_postgres"
    PGUSER         - Postgres role name. In production this is the app's
                     DATABRICKS_CLIENT_ID (service principal); for local dev,
                     use your own Databricks email instead.
    ENDPOINT_NAME  - full resource name, e.g.
                     "projects/<project-id>/branches/<branch-id>/endpoints/<endpoint-id>"

Optional:
    PGPORT         - default "5432"
    PGSSLMODE      - default "require"

If your app has Lakebase bound as an App resource, Databricks auto-injects
PGHOST/PGDATABASE/PGUSER/PGPORT/PGSSLMODE for you — only ENDPOINT_NAME needs
to be set explicitly in app.yaml.

One-time setup required in the Lakebase SQL editor before this will work —
see the bottom of this file for the SQL.
"""

import os
from contextlib import contextmanager

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine

_w = WorkspaceClient()

_PGHOST = os.environ.get("PGHOST")
_PGDATABASE = os.environ.get("PGDATABASE", "databricks_postgres")
_PGUSER = os.environ.get("PGUSER")
_PGPORT = os.environ.get("PGPORT", "5432")
_PGSSLMODE = os.environ.get("PGSSLMODE", "require")
_ENDPOINT_NAME = os.environ.get("ENDPOINT_NAME")


def _require_config():
    missing = [
        name
        for name, val in [
            ("PGHOST", _PGHOST),
            ("PGUSER", _PGUSER),
            ("ENDPOINT_NAME", _ENDPOINT_NAME),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(
            f"Missing required env var(s) for Lakebase: {', '.join(missing)}. "
            f"Set these in app.yaml (see lakebase.py docstring)."
        )


def _get_credential() -> str:
    """Generate a fresh OAuth database credential (token used as the password).

    Always generates a new one rather than caching — the connection pool below
    calls this per new connection, and Lakebase tokens are cheap to mint.
    """
    _require_config()
    try:
        credential = _w.postgres.generate_database_credential(endpoint=_ENDPOINT_NAME)
    except Exception as e:
        raise RuntimeError(
            f"Could not generate a database credential for endpoint "
            f"'{_ENDPOINT_NAME}'. Check that: (1) ENDPOINT_NAME matches the "
            f"exact resource name from the Lakebase branch's Computes tab, "
            f"and (2) the caller (your service principal, or you when testing "
            f"locally) has an OAuth-enabled Postgres role — see the SQL setup "
            f"at the bottom of lakebase.py. Original error: {e}"
        ) from e

    if not credential.token:
        raise RuntimeError("generate_database_credential() returned no token.")
    return credential.token


def _connection_kwargs() -> dict:
    _require_config()
    return {
        "host": _PGHOST,
        "port": _PGPORT,
        "dbname": _PGDATABASE,
        "user": _PGUSER,
        "password": _get_credential(),
        "sslmode": _PGSSLMODE,
    }


@contextmanager
def get_connection():
    """Yield a raw psycopg2 connection with a RealDictCursor factory, using a
    freshly-generated OAuth credential."""
    conn = psycopg2.connect(cursor_factory=RealDictCursor, **_connection_kwargs())
    try:
        yield conn
    finally:
        conn.close()


def _engine_creator():
    """Creator function so every new pooled connection gets a fresh, valid
    OAuth token instead of a baked-in password."""
    return psycopg2.connect(**_connection_kwargs())


def get_engine():
    """Return a SQLAlchemy engine for Lakebase.

    Uses a creator function so new connections always carry a valid token.
    pool_recycle forces pooled connections to be replaced every 30 minutes,
    comfortably under the ~1hr token lifetime.
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


# -----------------------------------------------------------------------------
# ONE-TIME SETUP (run once in the Lakebase SQL editor, as the project owner):
#
#   CREATE EXTENSION IF NOT EXISTS databricks_auth;
#
#   -- Replace with your app's DATABRICKS_CLIENT_ID (Environment tab in the
#   -- Databricks Apps UI), or your own email for local dev testing.
#   SELECT databricks_create_role('<DATABRICKS_CLIENT_ID_OR_EMAIL>', 'service_principal');
#
#   GRANT CONNECT ON DATABASE databricks_postgres TO "<DATABRICKS_CLIENT_ID_OR_EMAIL>";
#   GRANT CREATE, USAGE ON SCHEMA public TO "<DATABRICKS_CLIENT_ID_OR_EMAIL>";
#   GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public
#       TO "<DATABRICKS_CLIENT_ID_OR_EMAIL>";
#
# Without this, generate_database_credential() will succeed but psycopg2.connect()
# will fail with a Postgres authentication/permission error, since no matching
# OAuth-enabled role exists yet for the connecting identity.
# -----------------------------------------------------------------------------
