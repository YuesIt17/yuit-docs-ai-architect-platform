CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_decisions (
    id BIGSERIAL PRIMARY KEY,
    request_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    modality TEXT NOT NULL,
    model_uri TEXT,
    index_version TEXT,
    policy_version TEXT,
    tokens_in INT DEFAULT 0,
    tokens_out INT DEFAULT 0,
    cost_est NUMERIC(12, 6) DEFAULT 0,
    acl_decision TEXT NOT NULL,
    degraded BOOLEAN DEFAULT FALSE,
    latency_ms INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS label_assets (
    id UUID PRIMARY KEY,
    source_format TEXT NOT NULL,
    page_count INT DEFAULT 1,
    classification TEXT NOT NULL DEFAULT 'internal',
    s3_uri_raw TEXT,
    s3_uri_normalized TEXT,
    s3_uri_recognized TEXT,
    etag TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outbox (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    request JSONB,
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);