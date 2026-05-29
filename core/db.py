from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator


class PersistenceNotConfigured(RuntimeError):
    """Raised when a server-side persistent store is required but missing."""


def database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def database_configured() -> bool:
    return bool(database_url())


def is_vercel_runtime() -> bool:
    return os.getenv("VERCEL", "").strip() == "1"


def require_database() -> str:
    url = database_url()
    if not url:
        raise PersistenceNotConfigured("DATABASE_URL nao configurado.")
    return url


def _connect(row_factory: Any | None = None):
    try:
        import psycopg
    except ImportError as exc:
        raise PersistenceNotConfigured("Dependencia psycopg nao instalada.") from exc

    kwargs: dict[str, Any] = {"connect_timeout": 10}
    if row_factory is not None:
        kwargs["row_factory"] = row_factory
    return psycopg.connect(require_database(), **kwargs)


@contextmanager
def connection(row_factory: Any | None = None) -> Iterator[Any]:
    conn = _connect(row_factory=row_factory)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def jsonb(value: Any) -> Any:
    try:
        from psycopg.types.json import Jsonb
    except ImportError as exc:
        raise PersistenceNotConfigured("Dependencia psycopg nao instalada.") from exc
    return Jsonb(value)


def dict_row_factory() -> Any:
    try:
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise PersistenceNotConfigured("Dependencia psycopg nao instalada.") from exc
    return dict_row


def check_database() -> dict[str, Any]:
    configured = database_configured()
    if not configured:
        return {"configured": False, "ok": False, "error": "DATABASE_URL nao configurado."}
    try:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                cur.fetchone()
        return {"configured": True, "ok": True, "error": None}
    except Exception as exc:
        return {"configured": True, "ok": False, "error": str(exc)}
