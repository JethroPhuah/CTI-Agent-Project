-- =====================================================================
-- CTI Agent — Postgres schema
--   * iocs       : indicator of compromise database
--   * feedback   : user feedback (thumbs up/down) for offline training
--   * agent_runs : full trace of each agent run for replay/debugging
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------
-- IOCs
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS iocs (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    ioc_value    TEXT         NOT NULL,
    ioc_type     TEXT         NOT NULL CHECK (ioc_type IN
                              ('ipv4','ipv6','domain','url','md5','sha1','sha256','email','cve')),
    source       TEXT         NOT NULL,
    confidence   INTEGER      NOT NULL DEFAULT 50,  -- 0..100
    threat_level TEXT         NOT NULL DEFAULT 'unknown'
                              CHECK (threat_level IN ('critical','high','medium','low','unknown','benign')),
    tags         TEXT[]       DEFAULT '{}',
    description  TEXT,
    first_seen   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_seen    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    metadata     JSONB        DEFAULT '{}'::jsonb,
    UNIQUE (ioc_value, ioc_type)
);

CREATE INDEX IF NOT EXISTS idx_iocs_value      ON iocs (ioc_value);
CREATE INDEX IF NOT EXISTS idx_iocs_type       ON iocs (ioc_type);
CREATE INDEX IF NOT EXISTS idx_iocs_threat     ON iocs (threat_level);
CREATE INDEX IF NOT EXISTS idx_iocs_tags       ON iocs USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_iocs_metadata   ON iocs USING GIN (metadata);


-- ---------------------------------------------------------------------
-- Agent runs (full trace per query — drives the UI step view)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_runs (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_query   TEXT         NOT NULL,
    selected_tools TEXT[]     DEFAULT '{}',
    final_answer TEXT,
    steps        JSONB        NOT NULL DEFAULT '[]'::jsonb,
    started_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms  INTEGER,
    status       TEXT         NOT NULL DEFAULT 'running'
                              CHECK (status IN ('running','completed','failed'))
);
CREATE INDEX IF NOT EXISTS idx_runs_started ON agent_runs (started_at DESC);


-- ---------------------------------------------------------------------
-- Feedback (thumbs up/down for offline RLHF-style training)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id       UUID         REFERENCES agent_runs(id) ON DELETE CASCADE,
    rating       SMALLINT     NOT NULL CHECK (rating IN (-1, 1)),
    comment      TEXT,
    user_email   TEXT,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_feedback_run ON feedback (run_id);


-- ---------------------------------------------------------------------
-- Seed IOCs (so empty deployments still demo correctly)
-- ---------------------------------------------------------------------
INSERT INTO iocs (ioc_value, ioc_type, source, confidence, threat_level, tags, description) VALUES
  ('185.12.45.78',  'ipv4',   'Internal CTI', 90, 'high',
     ARRAY['apt41','c2','cobalt_strike'],
     'APT41 Cobalt Strike C2 IP, observed in 2024 cloud-targeting campaign'),
  ('91.92.249.110', 'ipv4',   'Internal CTI', 85, 'high',
     ARRAY['lockbit','ransomware','c2'],
     'LockBit 3.0 affiliate C2 IP, healthcare campaign'),
  ('45.135.232.94', 'ipv4',   'Internal CTI', 80, 'high',
     ARRAY['fin7','brute_ratel','c2'],
     'FIN7 / Brute Ratel C2 infrastructure'),
  ('198.51.100.42', 'ipv4',   'Internal CTI', 75, 'high',
     ARRAY['lazarus','dream_job','plugx'],
     'Lazarus Group Operation Dream Job infrastructure'),
  ('evil-cdn.example.org', 'domain', 'Internal CTI', 90, 'critical',
     ARRAY['apt41','shadowpad','c2'],
     'APT41 ShadowPad staging domain'),
  ('lockbitsupp.com', 'domain', 'Internal CTI', 95, 'critical',
     ARRAY['lockbit','leak_site'],
     'LockBit ransomware leak site'),
  ('5f4dcc3b5aa765d61d8327deb882cf99', 'md5', 'Internal CTI', 60, 'medium',
     ARRAY['apt41','dropper'], 'APT41 dropper sample'),
  ('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'sha256',
     'Internal CTI', 70, 'high',
     ARRAY['cobalt_strike','beacon'], 'Cobalt Strike beacon SHA-256'),
  ('CVE-2023-3519', 'cve', 'NVD', 100, 'critical',
     ARRAY['citrix','rce'], 'Citrix ADC/Gateway unauthenticated RCE'),
  ('CVE-2024-3400', 'cve', 'NVD', 100, 'critical',
     ARRAY['paloalto','panos','rce'], 'Palo Alto PAN-OS unauthenticated RCE')
ON CONFLICT (ioc_value, ioc_type) DO NOTHING;
