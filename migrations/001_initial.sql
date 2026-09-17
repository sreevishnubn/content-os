-- ContentOS production PostgreSQL schema
CREATE TABLE IF NOT EXISTS research_items (
    research_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    url TEXT,
    source_name TEXT,
    published_at TIMESTAMPTZ,
    discovered_at TIMESTAMPTZ NOT NULL,
    tags_json TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_research_items_url ON research_items(url) WHERE url IS NOT NULL;

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

CREATE TABLE IF NOT EXISTS content_scripts (
    script_id TEXT PRIMARY KEY,
    idea_id TEXT NOT NULL,
    title TEXT NOT NULL,
    hook TEXT NOT NULL,
    sections_json TEXT NOT NULL,
    closing TEXT NOT NULL,
    fact_check_json TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_content_scripts_idea ON content_scripts(idea_id);

CREATE TABLE IF NOT EXISTS production_jobs (
    production_id TEXT PRIMARY KEY,
    script_id TEXT NOT NULL,
    status TEXT NOT NULL,
    asset_paths_json TEXT NOT NULL,
    output_path TEXT,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_production_jobs_status ON production_jobs(status);

CREATE TABLE IF NOT EXISTS publish_requests (
    publish_id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    scheduled_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    external_id TEXT,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_publish_requests_status ON publish_requests(status);

CREATE TABLE IF NOT EXISTS video_metrics (
    metric_id TEXT PRIMARY KEY,
    external_video_id TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    views BIGINT NOT NULL DEFAULT 0,
    watch_time_minutes DOUBLE PRECISION NOT NULL DEFAULT 0,
    average_view_duration_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    impressions BIGINT NOT NULL DEFAULT 0,
    click_through_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
    likes BIGINT NOT NULL DEFAULT 0,
    comments BIGINT NOT NULL DEFAULT 0,
    subscribers_gained BIGINT NOT NULL DEFAULT 0,
    revenue DOUBLE PRECISION NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_video_metrics_video_time ON video_metrics(external_video_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS learning_signals (
    signal_id TEXT PRIMARY KEY,
    source_video_id TEXT,
    signal_type TEXT NOT NULL,
    observation TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_learning_signals_type ON learning_signals(signal_type);

CREATE TABLE IF NOT EXISTS automation_jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_automation_jobs_status ON automation_jobs(status);
