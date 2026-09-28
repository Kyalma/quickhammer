import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AdminGame, AdminPlayer, GameStatus } from "../api/types";

const STATUS_LABELS: Record<GameStatus, string> = {
  lobby: "Pending",
  active: "Running",
  finished: "Done",
};

export function AdminPage() {
  const [players, setPlayers] = useState<AdminPlayer[] | null>(null);
  const [games, setGames] = useState<AdminGame[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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

  if (error) return <p className="error">{error}</p>;
  if (!players || !games) return <p className="note">Loading…</p>;

  return (
    <>
      <h1>Admin</h1>

      <div className="card">
        <h2>Users ({players.length})</h2>
        <table className="breakdown">
          <thead>
            <tr><th>Name</th><th>Units</th><th>Role</th></tr>
          </thead>
          <tbody>
            {players.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td className="num">{p.unit_count}</td>
                <td className="detail">{p.is_admin ? "Admin" : "Player"}</td>
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
              <tr><th>Code</th><th>Status</th><th>Players</th><th>Progress</th></tr>
            </thead>
            <tbody>
              {games.map((g) => (
                <tr key={g.id}>
                  <td>{g.code}</td>
                  <td>
                    <span className={"ready-pill" + (g.status === "active" ? " ready" : "")}>
                      {STATUS_LABELS[g.status]}
                    </span>
                  </td>
                  <td className="detail">{g.player_names.join(", ") || "—"}</td>
                  <td className="detail">
                    {g.status === "active"
                      ? `Round ${g.current_round}, ${g.phase_name} (${g.active_player ?? "?"})`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

    </>
  );
}
