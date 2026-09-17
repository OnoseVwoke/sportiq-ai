import { useEffect, useState } from "react";

// Set in docker-compose.yml as VITE_API_URL. Falls back to localhost
// for running the frontend outside Docker during development.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:5000";

function App() {
  const [fixtures, setFixtures] = useState([]);
  const [bestPicks, setBestPicks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_URL}/fixtures`)
      .then((res) => {
        if (!res.ok) throw new Error(`Backend responded with ${res.status}`);
        return res.json();
      })
      .then((data) => setFixtures(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));

    fetch(`${API_URL}/best-picks`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setBestPicks(data))
      .catch(() => setBestPicks([]));
  }, []);

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <h1 style={styles.logo}>SportIQ AI</h1>
        <nav style={styles.nav}>
          <span>Predictions</span>
          <span>Statistics</span>
          <span>Form guide</span>
          <span>Odds</span>
        </nav>
      </header>

      <main style={styles.main}>
        {bestPicks.length > 0 && (
          <div style={styles.bestPicksPanel}>
            <h2 style={styles.bestPicksTitle}>Best picks (85%+ confidence)</h2>
            <div style={styles.bestPicksList}>
              {bestPicks.map((pick, i) => (
                <div key={i} style={styles.bestPickRow}>
                  <span>{pick.home_team} vs {pick.away_team}</span>
                  <span style={styles.bestPickCall}>
                    {formatMarket(pick.market)}: {formatPrediction(pick.prediction)} ({pick.confidence}%)
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <h2 style={styles.sectionTitle}>Today's fixtures</h2>

        {loading && <p>Loading fixtures...</p>}
        {error && (
          <p style={styles.error}>
            Couldn't reach the backend ({error}). Make sure the backend
            container is running.
          </p>
        )}
        {!loading && !error && fixtures.length === 0 && (
          <p>No fixtures yet — run the data-pipeline container to add sample data.</p>
        )}

        <div style={styles.fixtureList}>
          {fixtures.map((fx) => (
            <div key={fx.id} style={styles.fixtureCard}>
              <p style={styles.league}>{fx.league}</p>
              <p style={styles.match}>
                {fx.home_team} vs {fx.away_team}
              </p>
              <p style={styles.kickoff}>
                {new Date(fx.kickoff_time).toLocaleString()}
              </p>
              <span style={styles.status}>{fx.status}</span>
              {fx.result_prediction && (
                <div style={styles.markets}>
                  <div style={styles.marketRow}>
                    <span style={styles.marketLabel}>Result</span>
                    <span style={styles.marketPick}>
                      Our pick: {formatPrediction(fx.result_prediction)} ({fx.result_confidence}%)
                    </span>
                  </div>
                  {fx.btts_prediction && (
                    <div style={styles.marketRow}>
                      <span style={styles.marketLabel}>BTTS</span>
                      <span style={styles.marketPick}>
                        {formatPrediction(fx.btts_prediction)} ({fx.btts_confidence}%)
                      </span>
                    </div>
                  )}
                  {fx.over_2_5_prediction && (
                    <div style={styles.marketRow}>
                      <span style={styles.marketLabel}>O/U 2.5</span>
                      <span style={styles.marketPick}>
                        {formatPrediction(fx.over_2_5_prediction)} ({fx.over_2_5_confidence}%)
                      </span>
                    </div>
                  )}
                </div>
              )}
              {fx.home_odds && (
                <div style={styles.odds}>
                  <span>Home {fx.home_odds}</span>
                  {fx.draw_odds && <span>Draw {fx.draw_odds}</span>}
                  <span>Away {fx.away_odds}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

function formatPrediction(prediction) {
  const labels = {
    home_win: "Home win", draw: "Draw", away_win: "Away win",
    yes: "Yes", no: "No", over: "Over", under: "Under",
  };
  return labels[prediction] || prediction;
}

function formatMarket(market) {
  const labels = { match_result: "Result", btts: "BTTS", over_2_5: "O/U 2.5" };
  return labels[market] || market;
}

const styles = {
  page: { fontFamily: "system-ui, sans-serif", minHeight: "100vh", background: "#0f1115", color: "#e6e6e6" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px 24px", borderBottom: "1px solid #22252b" },
  logo: { margin: 0, fontSize: 20 },
  nav: { display: "flex", gap: 20, fontSize: 14, color: "#9aa0a6" },
  main: { padding: "24px" },
  sectionTitle: { fontSize: 16, color: "#9aa0a6", marginBottom: 16 },
  error: { color: "#f28b82" },
  fixtureList: { display: "flex", flexDirection: "column", gap: 12, maxWidth: 480 },
  fixtureCard: { background: "#1b1e24", borderRadius: 10, padding: 14 },
  league: { fontSize: 12, color: "#9aa0a6", margin: "0 0 4px" },
  match: { fontSize: 15, margin: "0 0 4px" },
  kickoff: { fontSize: 12, color: "#9aa0a6", margin: 0 },
  status: { fontSize: 11, color: "#8ab4f8" },
  markets: { marginTop: 8, display: "flex", flexDirection: "column", gap: 4 },
  marketRow: { display: "flex", justifyContent: "space-between", fontSize: 12 },
  marketLabel: { color: "#9aa0a6" },
  marketPick: { color: "#81c995", fontWeight: 500 },
  odds: { display: "flex", gap: 12, marginTop: 8, fontSize: 12, color: "#9aa0a6" },
  bestPicksPanel: { background: "#1b2a1e", border: "1px solid #2d4a33", borderRadius: 10, padding: 16, marginBottom: 24, maxWidth: 480 },
  bestPicksTitle: { fontSize: 14, color: "#81c995", margin: "0 0 10px" },
  bestPicksList: { display: "flex", flexDirection: "column", gap: 8 },
  bestPickRow: { display: "flex", justifyContent: "space-between", fontSize: 12, color: "#e6e6e6" },
  bestPickCall: { color: "#81c995", fontWeight: 500 },
};

export default App;
