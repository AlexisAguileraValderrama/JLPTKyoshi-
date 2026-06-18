import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "jlpt.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS notebooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subtitle TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS grammar_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notebook_id INTEGER NOT NULL,
            grammar_input TEXT NOT NULL,
            ai_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grammar_section_id INTEGER NOT NULL,
            user_input TEXT,
            ai_feedback TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (grammar_section_id) REFERENCES grammar_sections(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    # Migrate: add subtitle column if it doesn't exist yet
    cols = [r[1] for r in c.execute("PRAGMA table_info(notebooks)").fetchall()]
    if "subtitle" not in cols:
        c.execute("ALTER TABLE notebooks ADD COLUMN subtitle TEXT")
        conn.commit()
    conn.close()
