import { useEffect, useState } from "react";

// Set in docker-compose.yml as VITE_API_URL. Falls back to localhost
// for running the frontend outside Docker during development.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:5000";

function App() {
  const [fixtures, setFixtures] = useState([]);
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
            </div>
          ))}
        </div>
      </main>
    </div>
  );
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
};

export default App;
