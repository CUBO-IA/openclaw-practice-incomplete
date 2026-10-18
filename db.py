"""Conexión SQLite determinista: WAL + foreign_keys ON, filas como dict."""
from pathlib import Path
import sqlite3


def connect(db_path):
    """Abre la BD con journal WAL y claves foráneas activas."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


class Database:
    """Envoltura transaccional: confirma al salir bien, revierte en error."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.con = connect(db_path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.con.commit()
        else:
            self.con.rollback()
        self.con.close()
        return False
