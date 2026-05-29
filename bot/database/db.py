import os
import sqlite3
import json
import logging
from datetime import datetime
from bot.config import DATABASE_PATH

logger = logging.getLogger(__name__)


def get_connection():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            last_active TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT,
            original_name TEXT,
            file_type TEXT,
            page_count INTEGER DEFAULT 0,
            char_count INTEGER DEFAULT 0,
            uploaded_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER PRIMARY KEY,
            quiz_questions TEXT,
            quiz_index INTEGER DEFAULT 0,
            flashcard_deck TEXT,
            flashcard_index INTEGER DEFAULT 0,
            mode TEXT DEFAULT 'idle',
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized.")


def upsert_user(user_id: int, username: str, first_name: str):
    conn = get_connection()
    conn.execute("""
        INSERT INTO users (user_id, username, first_name, last_active)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(user_id) DO UPDATE SET
            last_active = datetime('now'),
            username = excluded.username
    """, (user_id, username, first_name))
    conn.commit()
    conn.close()


def add_document(user_id: int, filename: str, original_name: str, file_type: str, page_count: int, char_count: int):
    conn = get_connection()
    conn.execute("""
        INSERT INTO documents (user_id, filename, original_name, file_type, page_count, char_count)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, filename, original_name, file_type, page_count, char_count))
    conn.commit()
    conn.close()


def get_user_documents(user_id: int):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM documents WHERE user_id = ? ORDER BY uploaded_at DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_user_documents(user_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM documents WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_session(user_id: int) -> dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM sessions WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["quiz_questions"] = json.loads(d["quiz_questions"]) if d["quiz_questions"] else []
        d["flashcard_deck"] = json.loads(d["flashcard_deck"]) if d["flashcard_deck"] else []
        return d
    return {"user_id": user_id, "quiz_questions": [], "quiz_index": 0, "flashcard_deck": [], "flashcard_index": 0, "mode": "idle"}


def save_session(user_id: int, data: dict):
    conn = get_connection()
    conn.execute("""
        INSERT INTO sessions (user_id, quiz_questions, quiz_index, flashcard_deck, flashcard_index, mode, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(user_id) DO UPDATE SET
            quiz_questions = excluded.quiz_questions,
            quiz_index = excluded.quiz_index,
            flashcard_deck = excluded.flashcard_deck,
            flashcard_index = excluded.flashcard_index,
            mode = excluded.mode,
            updated_at = datetime('now')
    """, (
        user_id,
        json.dumps(data.get("quiz_questions", [])),
        data.get("quiz_index", 0),
        json.dumps(data.get("flashcard_deck", [])),
        data.get("flashcard_index", 0),
        data.get("mode", "idle")
    ))
    conn.commit()
    conn.close()
