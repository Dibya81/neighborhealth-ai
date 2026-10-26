-- NeighborHealth 2.0 schema (portable: SQLite + Postgres). Timestamps are ISO-8601 UTC strings.

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    phone TEXT,
    name TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'citizen',          -- citizen | official | admin
    language TEXT NOT NULL DEFAULT 'en',           -- en | kn | hi
    cohort TEXT,                                   -- pilot group code (e.g. an RWA), Step 8
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    ward_id TEXT,
    category TEXT NOT NULL,                        -- container | tyre | drain | construction | other
    description TEXT,
    photo_path TEXT,
    photo_hash TEXT,                               -- perceptual hash (dHash) for duplicate detection
    vision_label TEXT,                             -- likely_breeding_site | uncertain | unlikely | unavailable
    vision_score DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'pending',        -- pending | verified | rejected | duplicate | spam
    duplicate_of TEXT,
    flags TEXT,                                    -- JSON list of automatic flags
    created_at TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at);
CREATE INDEX IF NOT EXISTS idx_reports_ward ON reports(ward_id);
CREATE INDEX IF NOT EXISTS idx_reports_user ON reports(user_id);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    report_id TEXT REFERENCES reports(id),
    ward_id TEXT,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    kind TEXT NOT NULL DEFAULT 'inspection',       -- inspection | fogging | source_reduction
    priority INTEGER NOT NULL DEFAULT 2,           -- 1 high .. 3 low
    status TEXT NOT NULL DEFAULT 'open',           -- open | assigned | in_progress | inspected | cleared | closed
    team TEXT,
    route_id TEXT,
    notes TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

CREATE TABLE IF NOT EXISTS task_events (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    status TEXT NOT NULL,
    actor TEXT,
    note TEXT,
    at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS routes (
    id TEXT PRIMARY KEY,
    created_by TEXT,
    team TEXT,
    plan TEXT NOT NULL,                            -- JSON: ordered stops, ETAs, distances, method
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    label TEXT NOT NULL,                           -- home | office | school | other
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    radius_m INTEGER NOT NULL DEFAULT 1000,
    ward_ids TEXT NOT NULL,                        -- JSON list, computed at creation
    channels TEXT NOT NULL,                        -- JSON list: whatsapp | sms | email
    destination_phone TEXT,
    destination_email TEXT,
    language TEXT NOT NULL DEFAULT 'en',
    quiet_start TEXT DEFAULT '21:00',
    quiet_end TEXT DEFAULT '08:00',
    threshold_band TEXT NOT NULL DEFAULT 'high',
    active INTEGER NOT NULL DEFAULT 1,
    last_band TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    subscription_id TEXT NOT NULL REFERENCES subscriptions(id),
    user_id TEXT NOT NULL,
    ward_id TEXT,
    band TEXT NOT NULL,
    horizon INTEGER,
    dedupe_key TEXT UNIQUE NOT NULL,
    channel TEXT,
    status TEXT NOT NULL,                          -- queued | sent | suppressed | failed
    reason TEXT,
    deliver_after TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    feedback TEXT                                  -- useful | not_useful | unsubscribed
);
CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts(user_id, created_at);

CREATE TABLE IF NOT EXISTS chat_logs (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    kind TEXT NOT NULL,                            -- question | ward_explanation
    question TEXT,
    answer TEXT,
    citations TEXT,
    language TEXT,
    refused INTEGER DEFAULT 0,
    grounded INTEGER,
    created_at TEXT NOT NULL,
    feedback TEXT
);

CREATE TABLE IF NOT EXISTS consents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL,                            -- terms | alerts | pilot_research
    version TEXT NOT NULL,
    granted INTEGER NOT NULL,
    at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    session_id TEXT,
    name TEXT NOT NULL,
    props TEXT,
    at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_name ON events(name, at);
