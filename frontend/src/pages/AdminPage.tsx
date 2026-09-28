import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { GAME_STATUS_LABELS, type AdminGame, type AdminPlayer } from "../api/types";
import { useAuth } from "../context/AuthContext";

export function AdminPage() {
  const { player } = useAuth();
  const [players, setPlayers] = useState<AdminPlayer[] | null>(null);
  const [games, setGames] = useState<AdminGame[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    Promise.all([
      api.get<AdminPlayer[]>("/api/admin/players"),
      api.get<AdminGame[]>("/api/admin/games"),
    ])
      .then(([p, g]) => {
        setPlayers(p);
        setGames(g);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(refresh, [refresh]);

  async function remove(path: string, confirmMessage: string) {
    if (!window.confirm(confirmMessage)) return;
    setError(null);
    setBusy(true);
    try {
      await api.delete(path);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete that");
    } finally {
      setBusy(false);
    }
  }

  if (error && !players) return <p className="error">{error}</p>;
  if (!players || !games) return <p className="note">Loading…</p>;

  return (
    <>
      <h1>Admin</h1>
      {error && <p className="error">{error}</p>}

      <div className="card">
        <h2>Users ({players.length})</h2>
        <table className="breakdown">
          <thead>
            <tr><th>Name</th><th>Units</th><th>Role</th><th></th></tr>
          </thead>
          <tbody>
            {players.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td className="num">{p.unit_count}</td>
                <td className="detail">{p.is_admin ? "Admin" : "Player"}</td>
                <td>
                  {p.id === player?.id ? (
                    <span className="note">you</span>
                  ) : (
                    <button
                      className="danger"
                      disabled={busy}
                      onClick={() =>
                        remove(
                          `/api/admin/players/${p.id}`,
                          `Delete ${p.name}? Their units and their place in every game ` +
                            "go too. This cannot be undone.",
                        )
                      }
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Games ({games.length})</h2>
        {games.length === 0 && <p className="note">No games yet.</p>}
        {games.length > 0 && (
          <table className="breakdown">
            <thead>
              <tr><th>Code</th><th>Status</th><th>Players</th><th>Progress</th><th></th></tr>
            </thead>
            <tbody>
              {games.map((g) => (
                <tr key={g.id}>
                  <td>{g.code}</td>
                  <td>
                    <span className={"ready-pill" + (g.status === "active" ? " ready" : "")}>
                      {GAME_STATUS_LABELS[g.status]}
                    </span>
                  </td>
                  <td className="detail">{g.player_names.join(", ") || "—"}</td>
                  <td className="detail">
                    {g.status === "active"
                      ? `Round ${g.current_round}, ${g.phase_name} (${g.active_player ?? "?"})`
                      : "—"}
                  </td>
                  <td>
                    <button
                      className="danger"
                      disabled={busy}
                      onClick={() =>
                        remove(
                          `/api/admin/games/${g.id}`,
                          `Delete game ${g.code}? Rosters are kept. This cannot be undone.`,
                        )
                      }
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="note">
        Admin rights are granted from the server console:{" "}
        <code>docker exec -it QuickHammer python scripts/make_admin.py &lt;name&gt;</code>
      </p>
    </>
  );
}
