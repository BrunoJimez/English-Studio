import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("ENGLISH_STUDIO_DATA", ROOT / "data")).resolve()
DATA.mkdir(parents=True, exist_ok=True)
(DATA / "media").mkdir(exist_ok=True)
(DATA / "models").mkdir(exist_ok=True)


@contextmanager
def connect():
    db = sqlite3.connect(DATA / "studio.db", timeout=30)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()


def init_db():
    with connect() as db:
        db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS movies (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, original TEXT NOT NULL,
          duration REAL DEFAULT 0, status TEXT DEFAULT 'queued', progress REAL DEFAULT 0,
          message TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS segments (
          movie_id TEXT NOT NULL, idx INTEGER NOT NULL, start REAL NOT NULL, end REAL NOT NULL,
          text TEXT NOT NULL, words TEXT NOT NULL DEFAULT '[]', translation TEXT,
          PRIMARY KEY(movie_id, idx));
        CREATE TABLE IF NOT EXISTS attempts (
          id INTEGER PRIMARY KEY AUTOINCREMENT, movie_id TEXT NOT NULL,
          start REAL, end REAL, mode TEXT, answer TEXT, result TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY, movie_id TEXT, kind TEXT, status TEXT,
          progress REAL DEFAULT 0, message TEXT DEFAULT '');
        """)
        db.execute("UPDATE movies SET status='error', message='Processamento interrompido. Clique em tentar novamente.' WHERE status IN ('queued','processing')")
        db.execute("UPDATE jobs SET status='error', message='Interrompido ao fechar o aplicativo. Inicie novamente para continuar.' WHERE status IN ('queued','processing')")


def settings():
    defaults = {"whisper_model": "base.en", "device": "cpu", "ollama_model": "qwen3:8b"}
    with connect() as db:
        defaults.update({r["key"]: r["value"] for r in db.execute("SELECT * FROM settings")})
    return defaults


def movie(movie_id):
    with connect() as db:
        row = db.execute("SELECT * FROM movies WHERE id=?", (movie_id,)).fetchone()
    if not row:
        raise KeyError("Vídeo não encontrado.")
    return dict(row)


def segments(movie_id):
    with connect() as db:
        rows = db.execute("SELECT * FROM segments WHERE movie_id=? ORDER BY idx", (movie_id,)).fetchall()
    return [{**dict(r), "words": json.loads(r["words"])} for r in rows]


def update_movie(movie_id, **values):
    allowed = {"duration", "status", "progress", "message"}
    if not values or not set(values) <= allowed:
        raise ValueError("Invalid update")
    with connect() as db:
        db.execute(f"UPDATE movies SET {','.join(k+'=?' for k in values)} WHERE id=?", (*values.values(), movie_id))
