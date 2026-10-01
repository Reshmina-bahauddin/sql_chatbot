import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "retail.db"


def run_query(sql: str) -> list[dict]:
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(sql)
        rows = [dict(row) for row in cursor.fetchall()]
        return rows
    finally:
        conn.close()
