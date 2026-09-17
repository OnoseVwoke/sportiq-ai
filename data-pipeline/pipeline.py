"""
SportIQ AI — data pipeline

This is the container that runs on a schedule (via a cron job or
GitHub Actions / AWS EventBridge) to:
  1. Pull fixtures + odds from external sports APIs
  2. Save them into Postgres
  3. Run the prediction model and save its output

Step 1 (fixtures) pulls real data from football-data.org. Step 3
(predictions) now trains a real logistic regression model on
historical results each run and uses it to predict upcoming
fixtures — see train_model() and predict_match() below.
"""

import os
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


ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"


def normalize_team_name(name):
    """Strips common club suffixes so names from different data
    providers ('Arsenal FC' vs 'Arsenal') can be matched."""
    name = name.lower().strip()
    for suffix in (" fc", " afc", " cf"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()


def fetch_odds():
    """
    Pulls Premier League match-winner (h2h) odds from TheOddsAPI.
    Free tier: 500 requests/month.
    """
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "uk",
        "markets": "h2h",
        "oddsFormat": "decimal",
    }
    response = requests.get(ODDS_API_URL, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def average_h2h_odds(event):
    """Averages each outcome's price across every bookmaker offering it."""
    home_name = event["home_team"]
    away_name = event["away_team"]
    home_prices, draw_prices, away_prices = [], [], []

    for bookmaker in event.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market["key"] != "h2h":
                continue
            for outcome in market["outcomes"]:
                if outcome["name"] == home_name:
                    home_prices.append(outcome["price"])
                elif outcome["name"] == away_name:
                    away_prices.append(outcome["price"])
                elif outcome["name"] == "Draw":
                    draw_prices.append(outcome["price"])

    if not home_prices or not away_prices:
        return None

    return {
        "home": round(sum(home_prices) / len(home_prices), 2),
        "draw": round(sum(draw_prices) / len(draw_prices), 2) if draw_prices else None,
        "away": round(sum(away_prices) / len(away_prices), 2),
        "count": len(home_prices),
    }


def save_odds(events):
    """Matches each odds-API event to a fixture already in our DB
    (by normalized team name) and upserts the averaged odds."""
    saved = 0
    with engine.begin() as conn:
        fixtures = conn.execute(text("""
            SELECT f.id, ht.name AS home, at.name AS away
            FROM fixtures f
            JOIN teams ht ON ht.id = f.home_team_id
            JOIN teams at ON at.id = f.away_team_id
        """)).fetchall()
        fixture_lookup = [
            (row.id, normalize_team_name(row.home), normalize_team_name(row.away))
            for row in fixtures
        ]

        for event in events:
            odds = average_h2h_odds(event)
            if not odds:
                continue

            norm_home = normalize_team_name(event["home_team"])
            norm_away = normalize_team_name(event["away_team"])

            match_id = None
            for fid, fhome, faway in fixture_lookup:
                if (norm_home in fhome or fhome in norm_home) and (norm_away in faway or faway in norm_away):
                    match_id = fid
                    break
            if not match_id:
                continue

            conn.execute(text("""
                INSERT INTO odds (fixture_id, home_odds, draw_odds, away_odds, bookmaker_count, updated_at)
                VALUES (:fid, :home, :draw, :away, :count, NOW())
                ON CONFLICT (fixture_id) DO UPDATE SET
                    home_odds = EXCLUDED.home_odds,
                    draw_odds = EXCLUDED.draw_odds,
                    away_odds = EXCLUDED.away_odds,
                    bookmaker_count = EXCLUDED.bookmaker_count,
                    updated_at = NOW()
            """), {
                "fid": match_id, "home": odds["home"], "draw": odds["draw"],
                "away": odds["away"], "count": odds["count"],
            })
            saved += 1
    return saved


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


def fetch_historical_results(days_back=270):
    """
    Pulls finished Premier League matches from roughly the last 9
    months, to use as training data. Same API/endpoint as
    fetch_fixtures, just filtered to already-played matches.
    """
    headers = {"X-Auth-Token": SPORTS_API_KEY}
    today = datetime.utcnow().date()
    params = {
        "dateFrom": (today - timedelta(days=days_back)).isoformat(),
        "dateTo": today.isoformat(),
        "status": "FINISHED",
    }
    response = requests.get(API_FOOTBALL_URL, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    results = []
    for match in data.get("matches", []):
        score = match.get("score", {}).get("fullTime", {})
        if score.get("home") is None or score.get("away") is None:
            continue
        results.append({
            "home": match["homeTeam"]["name"],
            "away": match["awayTeam"]["name"],
            "home_goals": score["home"],
            "away_goals": score["away"],
        })
    return results


def compute_team_stats(results):
    """Each team's average goals scored and conceded across the
    historical results — a simple stand-in for 'team strength'."""
    raw = {}
    for r in results:
        raw.setdefault(r["home"], {"scored": [], "conceded": []})
        raw.setdefault(r["away"], {"scored": [], "conceded": []})
        raw[r["home"]]["scored"].append(r["home_goals"])
        raw[r["home"]]["conceded"].append(r["away_goals"])
        raw[r["away"]]["scored"].append(r["away_goals"])
        raw[r["away"]]["conceded"].append(r["home_goals"])

    return {
        team: {
            "avg_scored": sum(s["scored"]) / len(s["scored"]),
            "avg_conceded": sum(s["conceded"]) / len(s["conceded"]),
        }
        for team, s in raw.items()
    }


def build_training_data(results, team_stats):
    """Turns historical results into (features, outcome) pairs for training."""
    X, y = [], []
    for r in results:
        home_stats = team_stats.get(r["home"])
        away_stats = team_stats.get(r["away"])
        if not home_stats or not away_stats:
            continue
        X.append([
            home_stats["avg_scored"], home_stats["avg_conceded"],
            away_stats["avg_scored"], away_stats["avg_conceded"],
        ])
        if r["home_goals"] > r["away_goals"]:
            y.append("home_win")
        elif r["home_goals"] < r["away_goals"]:
            y.append("away_win")
        else:
            y.append("draw")
    return X, y


def train_model(X, y):
    """
    Trains a simple logistic regression classifier on team scoring
    averages. Retrained fresh on every pipeline run — the dataset
    is small enough (one season) that this is fast and always
    reflects the latest results, no model file to manage.
    """
    from sklearn.linear_model import LogisticRegression

    if len(X) < 20 or len(set(y)) < 2:
        # Not enough historical data yet to train meaningfully.
        return None

    model = LogisticRegression(max_iter=1000)
    model.fit(X, y)
    return model


def predict_match(model, team_stats, home_team, away_team):
    """
    Predicts one fixture's outcome using the trained model and the
    two teams' current scoring averages. Falls back to a neutral
    50/33/17-ish guess if we don't have enough data for one of the
    teams or the model itself (e.g. newly promoted side, or too
    early in a season).
    """
    home_stats = team_stats.get(home_team)
    away_stats = team_stats.get(away_team)

    if not model or not home_stats or not away_stats:
        return "home_win", 40.0  # conservative fallback, not a real prediction

    features = [[
        home_stats["avg_scored"], home_stats["avg_conceded"],
        away_stats["avg_scored"], away_stats["avg_conceded"],
    ]]
    probabilities = model.predict_proba(features)[0]
    classes = model.classes_
    best_idx = probabilities.argmax()
    outcome = str(classes[best_idx])
    confidence = round(float(probabilities[best_idx]) * 100, 2)
    return outcome, confidence


def predict_extra_markets(team_stats, home_team, away_team):
    """
    Estimates BTTS and Over/Under 2.5 goals using a Poisson goal
    model built from the same team scoring averages as the main
    result prediction — no extra API calls needed.
    """
    from scipy.stats import poisson

    home_stats = team_stats.get(home_team)
    away_stats = team_stats.get(away_team)
    if not home_stats or not away_stats:
        return []

    lambda_home = (home_stats["avg_scored"] + away_stats["avg_conceded"]) / 2
    lambda_away = (away_stats["avg_scored"] + home_stats["avg_conceded"]) / 2
    lambda_total = lambda_home + lambda_away

    p_home_scores = 1 - poisson.pmf(0, lambda_home)
    p_away_scores = 1 - poisson.pmf(0, lambda_away)
    p_btts = float(p_home_scores * p_away_scores)

    p_over_2_5 = float(1 - poisson.cdf(2, lambda_total))

    predictions = []
    if p_btts >= 0.5:
        predictions.append(("btts", "yes", round(p_btts * 100, 2)))
    else:
        predictions.append(("btts", "no", round((1 - p_btts) * 100, 2)))

    if p_over_2_5 >= 0.5:
        predictions.append(("over_2_5", "over", round(p_over_2_5 * 100, 2)))
    else:
        predictions.append(("over_2_5", "under", round((1 - p_over_2_5) * 100, 2)))

    return predictions


def save_predictions(fixture_ids, model, team_stats):
    with engine.begin() as conn:
        for fid in fixture_ids:
            row = conn.execute(
                text("""
                    SELECT ht.name AS home, at.name AS away
                    FROM fixtures f
                    JOIN teams ht ON ht.id = f.home_team_id
                    JOIN teams at ON at.id = f.away_team_id
                    WHERE f.id = :fid
                """),
                {"fid": fid},
            ).fetchone()
            if not row:
                continue

            outcome, confidence = predict_match(model, team_stats, row.home, row.away)
            all_predictions = [("match_result", outcome, confidence)]
            all_predictions += predict_extra_markets(team_stats, row.home, row.away)

            for market, prediction, conf in all_predictions:
                existing = conn.execute(
                    text("SELECT id FROM predictions WHERE fixture_id = :fid AND market = :market"),
                    {"fid": fid, "market": market},
                ).fetchone()
                if existing:
                    continue
                conn.execute(
                    text("""
                        INSERT INTO predictions (fixture_id, market, prediction, confidence)
                        VALUES (:fid, :market, :prediction, :confidence)
                    """),
                    {"fid": fid, "market": market, "prediction": prediction, "confidence": conf},
                )


def run():
    print("SportIQ AI pipeline: fetching fixtures...")
    fixtures = fetch_fixtures()
    fixture_ids = save_fixtures(fixtures)
    print(f"Saved {len(fixture_ids)} fixtures.")

    print("Fetching historical results to train the prediction model...")
    historical = fetch_historical_results()
    team_stats = compute_team_stats(historical)
    X, y = build_training_data(historical, team_stats)
    model = train_model(X, y)
    if model:
        print(f"Trained model on {len(X)} historical matches.")
    else:
        print("Not enough historical data to train a model yet — using fallback predictions.")

    print("Generating predictions...")
    save_predictions(fixture_ids, model, team_stats)

    print("Fetching odds...")
    try:
        events = fetch_odds()
        saved = save_odds(events)
        print(f"Saved odds for {saved} fixtures")
    except Exception as exc:
        # Odds are a nice-to-have on top of fixtures — don't let a
        # failed odds fetch take down the whole pipeline run.
        print(f"Odds fetch failed (continuing without odds): {exc}")

    print("Done.")


if __name__ == "__main__":
    run()
