"""
SportIQ AI — data pipeline

This is the container that runs on a schedule (via a cron job or
GitHub Actions / AWS EventBridge) to:
  1. Pull fixtures + odds from external sports APIs
  2. Save them into Postgres
  3. Run the prediction model and save its output

Step 1 (fixtures) now pulls real data from football-data.org. Step 3
(predictions) is still a placeholder random model — see the
`# TODO` marker below for where the real trained model plugs in.
"""

import os
import random
from datetime import datetime, timedelta

import requests
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ["DATABASE_URL"]
SPORTS_API_KEY = os.environ.get("SPORTS_API_KEY")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


API_FOOTBALL_URL = "https://api.football-data.org/v4/competitions/PL/matches"


def fetch_fixtures():
    """
    Pulls Premier League fixtures for the next 7 days from
    football-data.org. Free tier: 10 requests/minute, no
    restrictive monthly cap, and current-season data is
    actually included (unlike API-Football's free tier).
    """
    headers = {"X-Auth-Token": SPORTS_API_KEY}
    today = datetime.utcnow().date()
    params = {
        "dateFrom": today.isoformat(),
        "dateTo": (today + timedelta(days=7)).isoformat(),
    }

    response = requests.get(API_FOOTBALL_URL, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    fixtures = []
    for match in data.get("matches", []):
        fixtures.append({
            "league": "Premier League",
            "home": match["homeTeam"]["name"],
            "away": match["awayTeam"]["name"],
            "kickoff": datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")),
        })

    print(f"Found {len(fixtures)} fixtures in the next 7 days")
    return fixtures


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

            # Skip if this exact fixture (same teams + kickoff time) is
            # already saved, so re-running the pipeline doesn't pile up
            # duplicates.
            existing = conn.execute(
                text("""
                    SELECT id FROM fixtures
                    WHERE home_team_id = :home_id
                      AND away_team_id = :away_id
                      AND kickoff_time = :kickoff
                """),
                {"home_id": home_id, "away_id": away_id, "kickoff": fx["kickoff"]},
            ).fetchone()
            if existing:
                saved_ids.append(existing[0])
                continue

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
            existing = conn.execute(
                text("SELECT id FROM predictions WHERE fixture_id = :fid AND market = 'match_result'"),
                {"fid": fid},
            ).fetchone()
            if existing:
                continue

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