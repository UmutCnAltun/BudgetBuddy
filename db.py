import os
import sqlite3
from typing import Any, Iterable, Optional


DB_PATH = os.path.join(os.path.dirname(__file__), "BudgetBuddy.db")

_connection: Optional[sqlite3.Connection] = None


def get_connection() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(
            DB_PATH,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            check_same_thread=False,
        )
        _connection.row_factory = sqlite3.Row
        _enable_foreign_keys(_connection)
        init_db(_connection)
    return _connection


def _enable_foreign_keys(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON;")


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    if conn is None:
        conn = get_connection()

    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            total_amount REAL NOT NULL,
            start_date TEXT,
            end_date TEXT,
            frequency TEXT,
            currency TEXT DEFAULT 'TRY',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )

    cursor.execute("PRAGMA table_info(budgets);")
    columns = [row[1] for row in cursor.fetchall()]
    if "frequency" not in columns:
        cursor.execute("ALTER TABLE budgets ADD COLUMN frequency TEXT;")
    if "currency" not in columns:
        cursor.execute("ALTER TABLE budgets ADD COLUMN currency TEXT DEFAULT 'TRY';")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            budget_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            category TEXT,
            amount REAL NOT NULL,
            description TEXT,
            date TEXT,
            FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE
        );
        """
    )

    conn.commit()


def execute(
    query: str,
    params: Iterable[Any] = (),
    *,
    commit: bool = False,
) -> sqlite3.Cursor:
    conn = get_connection()
    cur = conn.execute(query, tuple(params))
    if commit:
        conn.commit()
    return cur


def executemany(
    query: str,
    seq_of_params: Iterable[Iterable[Any]],
    *,
    commit: bool = False,
) -> sqlite3.Cursor:
    conn = get_connection()
    cur = conn.executemany(query, list(map(tuple, seq_of_params)))
    if commit:
        conn.commit()
    return cur

