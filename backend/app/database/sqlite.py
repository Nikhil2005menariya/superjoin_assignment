import aiosqlite
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    filename    TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    file_size   INTEGER,
    page_count  INTEGER,
    status      TEXT DEFAULT 'queued',
    error_msg   TEXT,
    metadata    TEXT DEFAULT '{}',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    doc_id       TEXT NOT NULL REFERENCES documents(id),
    status       TEXT DEFAULT 'queued',
    stage        TEXT DEFAULT 'pending',
    progress     INTEGER DEFAULT 0,
    total_pages  INTEGER DEFAULT 0,
    current_page INTEGER DEFAULT 0,
    message      TEXT,
    error_msg    TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    id           TEXT PRIMARY KEY,
    doc_id       TEXT NOT NULL REFERENCES documents(id),
    parent_id    TEXT REFERENCES chunks(id),
    level        TEXT NOT NULL,
    page_num     INTEGER,
    section_path TEXT,
    raw_text     TEXT NOT NULL,
    bbox         TEXT DEFAULT '[]',
    source_type  TEXT DEFAULT 'text',
    chunk_index  INTEGER DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS facts (
    id                 TEXT PRIMARY KEY,
    doc_id             TEXT NOT NULL REFERENCES documents(id),
    chunk_id           TEXT REFERENCES chunks(id),
    statement          TEXT NOT NULL,
    subject            TEXT,
    predicate          TEXT,
    metric             TEXT,
    value_raw          TEXT,
    value_normalized   REAL,
    unit_raw           TEXT,
    unit_canonical     TEXT,
    time_period_raw    TEXT,
    time_start         DATE,
    time_end           DATE,
    scope              TEXT,
    qualifier          TEXT,
    fact_type          TEXT DEFAULT 'numerical',
    confidence         REAL DEFAULT 0.5,
    evidence_verified  INTEGER DEFAULT 0,
    exact_quote        TEXT,
    quote_start        INTEGER,
    quote_end          INTEGER,
    qdrant_point_id    TEXT,
    attributes         TEXT DEFAULT '{}',
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entities (
    id             TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,
    entity_type    TEXT,
    aliases        TEXT DEFAULT '[]',
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fact_entities (
    fact_id   TEXT NOT NULL REFERENCES facts(id),
    entity_id TEXT NOT NULL REFERENCES entities(id),
    role      TEXT DEFAULT 'subject',
    PRIMARY KEY (fact_id, entity_id)
);

CREATE TABLE IF NOT EXISTS relationships (
    id                     TEXT PRIMARY KEY,
    fact_a_id              TEXT NOT NULL REFERENCES facts(id),
    fact_b_id              TEXT NOT NULL REFERENCES facts(id),
    type                   TEXT NOT NULL,
    explanation            TEXT,
    reconciliation_context TEXT,
    confidence             REAL DEFAULT 0.5,
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc       ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_level     ON chunks(level);
CREATE INDEX IF NOT EXISTS idx_facts_doc        ON facts(doc_id);
CREATE INDEX IF NOT EXISTS idx_facts_subject    ON facts(subject);
CREATE INDEX IF NOT EXISTS idx_facts_verified   ON facts(evidence_verified);
CREATE INDEX IF NOT EXISTS idx_relationships_a  ON relationships(fact_a_id);
CREATE INDEX IF NOT EXISTS idx_relationships_b  ON relationships(fact_b_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(type);
CREATE INDEX IF NOT EXISTS idx_jobs_doc         ON jobs(doc_id);
"""


async def init_db():
    import os
    os.makedirs(settings.data_dir, exist_ok=True)
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()
    logger.info("SQLite database initialized at %s", settings.db_path)


async def get_db():
    return aiosqlite.connect(settings.db_path)
