"""
SportIQ AI — data pipeline

This is the container that runs on a schedule (via a cron job or
GitHub Actions / AWS EventBridge) to:
  1. Pull fixtures + odds from external sports APIs
  2. Save them into Postgres
  3. Run the prediction model and save its output

For now, step 1 and 3 are stubbed with placeholder logic so the
whole pipeline runs end-to-end. Swap in real API calls and a real
model once you have API keys and training data (see the two
`# TODO` markers below).
"""

import os
import random
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text

DATABASE_URL = os.environ["DATABASE_URL"]
SPORTS_API_KEY = os.environ.get("SPORTS_API_KEY")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def fetch_fixtures():
    """
    TODO: replace with a real call to API-Football (or similar):
        https://www.api-football.com/documentation-v3#tag/Fixtures
    For now, returns a couple of placeholder fixtures so the rest
    of the pipeline has something to work with.
    """
    now = datetime.utcnow()
    return [
        {"league": "Premier League", "home": "Man City", "away": "Liverpool",
         "kickoff": now + timedelta(hours=3)},
        {"league": "La Liga", "home": "Real Madrid", "away": "Sevilla",
         "kickoff": now + timedelta(hours=5)},
    ]


def get_or_create_team(conn, name, league):
    row = conn.execute(
        text("SELECT id FROM teams WHERE name = :name AND league = :league"),
        {"name": name, "league": league},
    ).fetchone()
    if row:
        return row[0]
    result = conn.execute(
        text("INSERT INTO teams (name, league) VALUES (:name, :league) RETURNING id"),
        {"name": name, "league": league},
    )
    return result.fetchone()[0]


def save_fixtures(fixtures):
    saved_ids = []
    with engine.begin() as conn:
        for fx in fixtures:
            home_id = get_or_create_team(conn, fx["home"], fx["league"])
            away_id = get_or_create_team(conn, fx["away"], fx["league"])
            result = conn.execute(
                text("""
                    INSERT INTO fixtures (league, home_team_id, away_team_id, kickoff_time)
                    VALUES (:league, :home_id, :away_id, :kickoff)
                    RETURNING id
                """),
                {"league": fx["league"], "home_id": home_id, "away_id": away_id, "kickoff": fx["kickoff"]},
            )
            saved_ids.append(result.fetchone()[0])
    return saved_ids


def predict(fixture_id):
    """
    TODO: replace with a real model — start with a simple
    scikit-learn / XGBoost classifier trained on historical
    results + odds (see Phase 1 of the build plan). This
    placeholder just picks a random confidence so the API and
    frontend have real rows to display while the model is built.
    """
    outcome = random.choice(["home_win", "draw", "away_win"])
    confidence = round(random.uniform(45, 80), 2)
    return outcome, confidence


def save_predictions(fixture_ids):
    with engine.begin() as conn:
        for fid in fixture_ids:
            outcome, confidence = predict(fid)
            conn.execute(
                text("""
                    INSERT INTO predictions (fixture_id, market, prediction, confidence)
                    VALUES (:fid, 'match_result', :prediction, :confidence)
                """),
                {"fid": fid, "prediction": outcome, "confidence": confidence},
            )


def run():
    print("SportIQ AI pipeline: fetching fixtures...")
    fixtures = fetch_fixtures()
    fixture_ids = save_fixtures(fixtures)
    print(f"Saved {len(fixture_ids)} fixtures. Generating predictions...")
    save_predictions(fixture_ids)
    print("Done.")


if __name__ == "__main__":
    run()
