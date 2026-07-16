# -*- coding: utf-8 -*-
"""
NewsPilot AI v2 — Database Layer (SQLite)
Single source of truth for articles, categories and pipeline state.
"""

import sqlite3
import os
import json
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "newspilot.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row           # rows accessible as dicts
    conn.execute("PRAGMA journal_mode=WAL")  # safe concurrent reads/writes
    return conn


def init_db():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT    UNIQUE NOT NULL,
                headline    TEXT,
                summary     TEXT,
                category    TEXT,
                sentiment   TEXT    DEFAULT 'Neutral',
                image_url   TEXT,
                source_name TEXT,
                published_at TEXT,
                fetched_at  TEXT    DEFAULT (datetime('now')),
                is_active   INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS pipeline_state (
                id          INTEGER PRIMARY KEY CHECK (id = 1),
                stage       TEXT    DEFAULT 'idle',
                percent     INTEGER DEFAULT 0,
                last_run    TEXT,
                articles_found INTEGER DEFAULT 0,
                articles_saved INTEGER DEFAULT 0,
                error       TEXT
            );

            -- Ensure exactly one pipeline state row
            INSERT OR IGNORE INTO pipeline_state (id, stage, percent) VALUES (1, 'idle', 0);

            CREATE INDEX IF NOT EXISTS idx_category  ON articles (category);
            CREATE INDEX IF NOT EXISTS idx_published ON articles (published_at DESC);
        """)


def upsert_article(article: dict):
    """Insert or update an article (by URL)."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO articles
                (url, headline, summary, category, sentiment, image_url, source_name, published_at)
            VALUES
                (:url, :headline, :summary, :category, :sentiment, :image_url, :source_name, :published_at)
            ON CONFLICT(url) DO UPDATE SET
                headline    = excluded.headline,
                summary     = excluded.summary,
                category    = excluded.category,
                sentiment   = excluded.sentiment,
                image_url   = excluded.image_url,
                fetched_at  = datetime('now'),
                is_active   = 1
        """, article)


def get_articles(category: str = None, search: str = None,
                 page: int = 1, limit: int = 12) -> list:
    """Paginated article query with optional category filter and search."""
    offset = (page - 1) * limit
    params = []
    where_clauses = ["is_active = 1"]

    if category and category.lower() != "all":
        where_clauses.append("category = ?")
        params.append(category)

    if search:
        where_clauses.append("(headline LIKE ? OR summary LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]

    where = " AND ".join(where_clauses)
    params += [limit, offset]

    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT id, headline, summary, category, sentiment,
                   image_url, source_name, published_at, fetched_at
            FROM articles
            WHERE {where}
            ORDER BY published_at DESC, fetched_at DESC
            LIMIT ? OFFSET ?
        """, params).fetchall()

    return [dict(r) for r in rows]


def get_categories() -> list:
    """Return categories that have at least one active article."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT DISTINCT category FROM articles
            WHERE is_active = 1 AND category IS NOT NULL
            ORDER BY category
        """).fetchall()
    return ["All"] + [r["category"] for r in rows]


def update_pipeline_state(stage: str, percent: int,
                           articles_found: int = 0, articles_saved: int = 0,
                           error: str = None):
    ts = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("""
            UPDATE pipeline_state SET
                stage = ?, percent = ?, articles_found = ?,
                articles_saved = ?, error = ?, last_run = ?
            WHERE id = 1
        """, (stage, percent, articles_found, articles_saved, error, ts))


def get_pipeline_state() -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM pipeline_state WHERE id = 1").fetchone()
    return dict(row) if row else {}
