import os
import sqlite3
from typing import Any, Literal

db_path = os.path.join(os.path.dirname(__file__), "database.db")


def get_db() -> sqlite3.Connection:
    if not hasattr(get_db, "db"):
        db = sqlite3.connect(db_path)
        get_db.db = db

    return get_db.db


def fetch_all(sql: Literal[str], params: tuple[Any, ...] | None = None) -> list[dict]:
    cursor = _get_cursor(sql, params)
    rows = cursor.fetchall()
    results = []
    for row_ in rows:
        results.append(_get_result_with_column_names(cursor, row_))
    cursor.close()
    return results


def fetch_one(sql: Literal[str], params: tuple[Any, ...] | None = None) -> dict | None:
    cursor = _get_cursor(sql, params)
    row_ = cursor.fetchone()
    if not row_:
        cursor.close()
        return None
    row = _get_result_with_column_names(cursor, row_)
    cursor.close()
    return row


def execute(sql: Literal[str], params: tuple[Any, ...] | None = None, autocommit: bool = True) -> None:
    db = get_db()
    args: tuple[Literal[str], tuple[Any, ...] | None] = (sql, params)
    cursor = db.cursor()
    cursor.execute(*args)
    if autocommit:
        db.commit()


def close_db() -> None:
    _close_db()


def _close_db() -> None:
    get_db().close()


def _get_cursor(sql: Literal[str], params: tuple[Any, ...] | None) -> sqlite3.Cursor:
    db = get_db()
    args: tuple[Literal[str], tuple[Any, ...] | None] = (sql, params)
    cursor = db.cursor()
    cursor.execute(*args)
    return cursor


def _get_result_with_column_names(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict:
    column_names = [d[0] for d in cursor.description]
    resulting_row = {}
    for index, column_name in enumerate(column_names):
        resulting_row[column_name] = row[index]
    return resulting_row


def create() -> None:
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        status TEXT,
        qr_code TEXT
    );
    """
    execute(create_table_sql, params=())