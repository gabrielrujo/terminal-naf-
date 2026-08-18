"""Conexão SQLite e inicialização do schema."""

import sqlite3

from flask import current_app, g


def get_db():
    if "db_v2" not in g:
        connection = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        g.db_v2 = connection
    return g.db_v2


def close_db(_exception=None):
    connection = g.pop("db_v2", None)
    if connection is not None:
        connection.close()


def init_db():
    connection = get_db()
    with current_app.open_resource("schema.sql") as schema:
        connection.executescript(schema.read().decode("utf-8"))
    connection.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
