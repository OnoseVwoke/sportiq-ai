import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

app = FastAPI(title="SportIQ AI API")

# Allow the frontend container to call this API during local dev.
# Lock this down to your real domain before going to production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/fixtures")
def get_fixtures(league: str | None = None, status: str | None = None):
    """
    Returns fixtures, optionally filtered by league or status
    (scheduled | live | finished). This is what the homepage's
    match list and live-scores bar both read from. Includes
    averaged match-winner odds where available.
    """
    query = """
        SELECT f.id, f.league, ht.name AS home_team, at.name AS away_team,
               f.kickoff_time, f.status, f.home_score, f.away_score,
               o.home_odds, o.draw_odds, o.away_odds, o.bookmaker_count
        FROM fixtures f
        JOIN teams ht ON ht.id = f.home_team_id
        JOIN teams at ON at.id = f.away_team_id
        LEFT JOIN odds o ON o.fixture_id = f.id
        WHERE (:league IS NULL OR f.league = :league)
          AND (:status IS NULL OR f.status = :status)
        ORDER BY f.kickoff_time ASC
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query), {"league": league, "status": status}).mappings().all()
    return [dict(r) for r in rows]


@app.get("/predictions/{fixture_id}")
def get_predictions(fixture_id: int):
    """Returns all market predictions (result, BTTS, over/under, etc.) for one fixture."""
    query = """
        SELECT market, prediction, confidence, created_at
        FROM predictions
        WHERE fixture_id = :fixture_id
        ORDER BY created_at DESC
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query), {"fixture_id": fixture_id}).mappings().all()
    return [dict(r) for r in rows]
