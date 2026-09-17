-- Core schema for SportIQ AI. Kept intentionally simple for v1 —
-- more tables (injuries, referees, live_events) get added in later phases.

CREATE TABLE IF NOT EXISTS teams (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    league TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fixtures (
    id SERIAL PRIMARY KEY,
    league TEXT NOT NULL,
    home_team_id INTEGER REFERENCES teams(id),
    away_team_id INTEGER REFERENCES teams(id),
    kickoff_time TIMESTAMP NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled', -- scheduled | live | finished
    home_score INTEGER,
    away_score INTEGER
);

CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    fixture_id INTEGER REFERENCES fixtures(id),
    market TEXT NOT NULL,          -- e.g. 'match_result', 'btts', 'over_2_5'
    prediction TEXT NOT NULL,      -- e.g. 'home_win', 'yes', 'over'
    confidence NUMERIC(5,2) NOT NULL, -- 0.00 - 100.00
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS odds (
    id SERIAL PRIMARY KEY,
    fixture_id INTEGER REFERENCES fixtures(id) UNIQUE,
    home_odds NUMERIC(6,2),
    draw_odds NUMERIC(6,2),
    away_odds NUMERIC(6,2),
    bookmaker_count INTEGER,       -- how many bookmakers these are averaged across
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    subscription_tier TEXT NOT NULL DEFAULT 'free', -- free | premium
    created_at TIMESTAMP DEFAULT NOW()
);