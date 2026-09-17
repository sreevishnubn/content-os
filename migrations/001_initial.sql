-- ContentOS production schema, PostgreSQL
CREATE TABLE IF NOT EXISTS content_ideas (
    idea_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    topic TEXT NOT NULL,
    audience TEXT NOT NULL,
    hook TEXT NOT NULL,
    source TEXT,
    why_now TEXT,
    monetization_angle TEXT,
    demand DOUBLE PRECISION NOT NULL,
    curiosity DOUBLE PRECISION NOT NULL,
    competition DOUBLE PRECISION NOT NULL,
    monetization DOUBLE PRECISION NOT NULL,
    production DOUBLE PRECISION NOT NULL,
    overall_score DOUBLE PRECISION,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_content_ideas_status ON content_ideas(status);
CREATE INDEX IF NOT EXISTS idx_content_ideas_score ON content_ideas(overall_score DESC);
