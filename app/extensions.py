"""MELODYX — Database helpers (SQLite, WAL mode)."""

import sqlite3
from typing import Optional

from flask import Flask, g, current_app


def get_db() -> sqlite3.Connection:
    """Return the per-request SQLite connection, creating one if needed.

    The connection uses WAL journal mode for better concurrency and
    ``sqlite3.Row`` as its row factory so that rows behave like dicts.
    """
    if "db" not in g:
        db_path: str = current_app.config["DATABASE_PATH"]
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        g.db = conn
    return g.db


def close_db(e: Optional[BaseException] = None) -> None:
    """Close the SQLite connection stored on *g*, if any.

    Registered as a ``teardown_appcontext`` callback by the application
    factory so it runs automatically at the end of every request.
    """
    db: Optional[sqlite3.Connection] = g.pop("db", None)
    if db is not None:
        db.close()


def init_extensions(app: Flask) -> None:
    """Register database teardown with the Flask application."""
    app.teardown_appcontext(close_db)
