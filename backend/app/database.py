import sqlite3
from contextlib import contextmanager
from app.config import DB_PATH

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    full_name TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    role_title TEXT,
    headline_summary TEXT,
    tone_preset TEXT DEFAULT 'professional_concise',
    visibility TEXT DEFAULT 'private',          -- public | unlisted | private (7.1)
    published INTEGER DEFAULT 0,
    public_slug TEXT UNIQUE,
    last_indexed_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clone_id INTEGER NOT NULL REFERENCES clones(id),
    doc_type TEXT NOT NULL,            -- resume | linkedin | certificate | project_link
    original_filename TEXT,
    storage_path TEXT,
    source_url TEXT,
    raw_extracted_text TEXT,
    confirmed_text TEXT,               -- FR-1.5: owner-reviewed/corrected content
    confirmed INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',     -- pending | parsed | confirmed | failed
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clone_id INTEGER NOT NULL REFERENCES clones(id),
    document_id INTEGER NOT NULL REFERENCES documents(id),
    chunk_text TEXT NOT NULL,
    vector_index_position INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clone_id INTEGER NOT NULL REFERENCES clones(id),
    visitor_name TEXT,
    visitor_email TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,                -- visitor | clone
    content TEXT NOT NULL,
    grounded INTEGER DEFAULT 0,        -- did response cite a source chunk? (FR-2.3 / success metric)
    source_document_ids TEXT,          -- JSON list of document ids cited (FR-3.3)
    unanswerable INTEGER DEFAULT 0,    -- FR-4.2: gap tracking
    flagged_inaccurate INTEGER DEFAULT 0,  -- FR-4.3
    owner_correction TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized at", DB_PATH)
