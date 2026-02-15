-- GhostRadar schema
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    plan TEXT DEFAULT 'free' CHECK (plan IN ('free','monthly','lifetime')),
    unlocked_until TIMESTAMP,
    free_scans_used_today INT DEFAULT 0,
    free_scans_day DATE DEFAULT CURRENT_DATE,
    last_seen TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    message_text TEXT NOT NULL,
    direction TEXT DEFAULT 'they' CHECK (direction IN ('they','me')),
    interest_score INT,
    red_flag_risk INT,
    emotional_distance INT,
    ghost_probability INT,
    reply_window TEXT,
    confidence TEXT,
    hidden_signals_count INT DEFAULT 0,
    hidden_signals JSONB DEFAULT '[]',
    archetype TEXT,
    summary TEXT,
    replies JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    event_name TEXT NOT NULL,
    meta JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS stripe_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    stripe_session_id TEXT UNIQUE,
    plan TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_device ON users(device_id);
CREATE INDEX IF NOT EXISTS idx_scans_user ON scans(user_id);
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_stripe_user ON stripe_sessions(user_id);
