-- ============================================================
-- NeighborHealth — Complete Supabase / PostgreSQL Schema
-- Run this ENTIRE block in Supabase Dashboard → SQL Editor
-- Safe to re-run: uses IF NOT EXISTS / ON CONFLICT DO NOTHING
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── 1. wards ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wards (
    id                  VARCHAR(10)     PRIMARY KEY,
    name                VARCHAR(100)    NOT NULL,
    constituency        VARCHAR(100),
    population          INTEGER,
    population_density  NUMERIC(8,2),
    area_sqkm           NUMERIC(6,2),
    created_at          TIMESTAMPTZ     DEFAULT NOW()
);

-- ── 2. diseases ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diseases (
    id          VARCHAR(30)     PRIMARY KEY,
    name        VARCHAR(100)    NOT NULL,
    category    VARCHAR(30)     CHECK (category IN ('vector','water','heat','respiratory')),
    season      VARCHAR(30)     CHECK (season IN ('monsoon','summer','winter','all_year')),
    model_type  VARCHAR(20)     CHECK (model_type IN ('ml','hybrid','rule_based')),
    peak_months INTEGER[],
    created_at  TIMESTAMPTZ     DEFAULT NOW()
);

INSERT INTO diseases (id, name, category, season, model_type, peak_months) VALUES
    ('dengue',            'Dengue',            'vector',       'monsoon',   'ml',         ARRAY[7,8,9,10,11]),
    ('malaria',           'Malaria',           'vector',       'monsoon',   'hybrid',      ARRAY[6,7,8,9,10]),
    ('cholera',           'Cholera',           'water',        'monsoon',   'rule_based',  ARRAY[6,7,8,9]),
    ('typhoid',           'Typhoid',           'water',        'monsoon',   'rule_based',  ARRAY[6,7,8,9]),
    ('hepatitis_a',       'Hepatitis A',       'water',        'monsoon',   'rule_based',  ARRAY[7,8,9]),
    ('heatstroke',        'Heatstroke',        'heat',         'summer',    'rule_based',  ARRAY[3,4,5,6]),
    ('heat_exhaustion',   'Heat Exhaustion',   'heat',         'summer',    'rule_based',  ARRAY[3,4,5,6]),
    ('dehydration',       'Dehydration',       'heat',         'summer',    'rule_based',  ARRAY[3,4,5,6]),
    ('common_cold',       'Common Cold',       'respiratory',  'winter',    'rule_based',  ARRAY[11,12,1,2]),
    ('bronchitis',        'Bronchitis',        'respiratory',  'winter',    'rule_based',  ARRAY[11,12,1,2]),
    ('allergic_rhinitis', 'Allergic Rhinitis', 'respiratory',  'all_year',  'rule_based',  ARRAY[1,2,3,10,11,12]),
    ('copd',              'COPD',              'respiratory',  'all_year',  'rule_based',  ARRAY[11,12,1,2,3])
ON CONFLICT (id) DO NOTHING;

-- ── 3. ward_risk_scores ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS ward_risk_scores (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    ward_id         VARCHAR(10)     NOT NULL REFERENCES wards(id) ON DELETE CASCADE,
    disease_id      VARCHAR(30)     NOT NULL REFERENCES diseases(id) ON DELETE CASCADE,
    score_date      DATE            NOT NULL,
    risk_score      NUMERIC(5,2)    NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),
    risk_level      VARCHAR(10)     NOT NULL CHECK (risk_level IN ('low','medium','high')),
    rainfall_7d     NUMERIC(7,2),
    temp_avg        NUMERIC(5,2),
    humidity_avg    NUMERIC(5,2),
    dengue_cases    INTEGER         DEFAULT 0,
    report_count    INTEGER         DEFAULT 0,
    model_version   VARCHAR(30)     DEFAULT 'v1-ml+disease-hybrid',
    ai_reason       JSONB,
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    UNIQUE (ward_id, disease_id, score_date)
);

CREATE INDEX IF NOT EXISTS idx_risk_ward_disease_date
    ON ward_risk_scores(ward_id, disease_id, score_date DESC);
CREATE INDEX IF NOT EXISTS idx_risk_disease_date
    ON ward_risk_scores(disease_id, score_date DESC);
CREATE INDEX IF NOT EXISTS idx_risk_date
    ON ward_risk_scores(score_date DESC);

-- ── 4. breeding_reports ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS breeding_reports (
    id          UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    ward_id     VARCHAR(10)     REFERENCES wards(id) ON DELETE CASCADE,
    lat         NUMERIC(9,6)    NOT NULL,
    lng         NUMERIC(9,6)    NOT NULL,
    description TEXT,
    photo_url   VARCHAR(500),
    ip_hash     VARCHAR(64),
    status      VARCHAR(20)     DEFAULT 'pending'
                                CHECK (status IN ('pending','verified','spam')),
    reported_at TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_ward_date
    ON breeding_reports(ward_id, reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_date
    ON breeding_reports(reported_at DESC);

-- ── 5. users ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(100),
    email               VARCHAR(200)    UNIQUE,
    phone               VARCHAR(20),
    lat                 NUMERIC(9,6),
    lng                 NUMERIC(9,6),
    home_ward_id        VARCHAR(10)     REFERENCES wards(id),
    health_conditions   TEXT[]          DEFAULT '{}',
    saved_locations     JSONB           DEFAULT '[]',
    created_at          TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email    ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_firebase ON users(id);

-- ── 6. subscriptions ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subscriptions (
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID            REFERENCES users(id) ON DELETE SET NULL,
    ward_id             VARCHAR(10)     NOT NULL REFERENCES wards(id) ON DELETE CASCADE,
    contact             VARCHAR(200)    NOT NULL,
    contact_type        VARCHAR(10)     NOT NULL CHECK (contact_type IN ('sms','email')),
    name                VARCHAR(100),
    email               VARCHAR(200),
    notify_diseases     TEXT[]          DEFAULT ARRAY['dengue'],
    threshold           INTEGER         DEFAULT 70 CHECK (threshold BETWEEN 1 AND 100),
    active              BOOLEAN         DEFAULT TRUE,
    created_at          TIMESTAMPTZ     DEFAULT NOW(),
    UNIQUE (ward_id, contact)
);

CREATE INDEX IF NOT EXISTS idx_subs_ward_active
    ON subscriptions(ward_id) WHERE active = TRUE;
CREATE INDEX IF NOT EXISTS idx_subs_user
    ON subscriptions(user_id);

-- ── 7. alert_log ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_log (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    subscription_id UUID            NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    ward_id         VARCHAR(10),
    disease_id      VARCHAR(30)     DEFAULT 'dengue',
    risk_score      NUMERIC(5,2),
    channel         VARCHAR(10),
    sent_at         TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_log_sub_date
    ON alert_log(subscription_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_log_disease
    ON alert_log(disease_id, sent_at DESC);

-- ── 8. weather_cache ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS weather_cache (
    id          UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    fetch_date  DATE            NOT NULL UNIQUE,
    raw_payload JSONB           NOT NULL,
    fetched_at  TIMESTAMPTZ     DEFAULT NOW()
);

-- ── 9. active_alerts ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS active_alerts (
    id          UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_date  DATE            NOT NULL,
    source      VARCHAR(100),
    headline    TEXT            NOT NULL,
    details     TEXT,
    severity    VARCHAR(20)     CHECK (severity IN ('low','medium','high')),
    disease_tags TEXT[],
    fetched_at  TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_date
    ON active_alerts(alert_date DESC);

-- ── 10. ai_suggestions ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_suggestions (
    id          UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ward_id     VARCHAR(10),
    disease_id  VARCHAR(30),
    message     TEXT            NOT NULL,
    response    TEXT            NOT NULL,
    context     JSONB           DEFAULT '{}',
    created_at  TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_suggestions_user
    ON ai_suggestions(user_id, created_at DESC);

-- ── Verify ────────────────────────────────────────────────────
SELECT table_name,
       (SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = t.table_name AND table_schema = 'public') AS column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN (
    'wards','diseases','ward_risk_scores','breeding_reports',
    'users','subscriptions','alert_log','weather_cache',
    'active_alerts','ai_suggestions'
  )
ORDER BY table_name;
