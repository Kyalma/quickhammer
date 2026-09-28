import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { GAME_STATUS_LABELS, type Game, type GameSummary } from "../api/types";
import { usePolling } from "../hooks/usePolling";

const POLL_MS = 4000;

export function LobbyPage() {
  const navigate = useNavigate();
  const [games, setGames] = useState<GameSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    api
      .get<GameSummary[]>("/api/games")
      .then(setGames)
      .catch((err) => setError(err.message));
  }, []);

  // Keep the list fresh so games others open appear without a reload.
  usePolling(refresh, POLL_MS);

  async function createGame() {
    setError(null);
    setBusy(true);
    try {
      const game = await api.post<Game>("/api/games");
      navigate(`/games/${game.code}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create game");
    } finally {
      setBusy(false);
    }
  }

  async function joinGame(code: string) {
    setError(null);
    setBusy(true);
    try {
      await api.post<Game>(`/api/games/${code}/join`);
      navigate(`/games/${code}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not join game");
      setBusy(false);
    }
  }

  async function deleteGame(game: GameSummary) {
    if (!window.confirm(`Delete game ${game.code}? This cannot be undone.`)) return;
    setError(null);
    setBusy(true);
    try {
      await api.delete(`/api/games/${game.code}`);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete game");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="row" style={{ alignItems: "center", marginBottom: "1rem" }}>
        <h1 style={{ flex: 1 }}>Play</h1>
        <button className="primary" style={{ flex: "0 0 auto" }} disabled={busy} onClick={createGame}>
          + New game
        </button>
      </div>
      {error && <p className="error">{error}</p>}

      {games && games.length === 0 && (
        <p className="note">No games yet. Create one and share it with your opponents.</p>
      )}
      {!games && !error && <p className="note">Loading games…</p>}

      {games?.map((game) => (
        <div className="card" key={game.id}>
          <div className="unit-state-head">
            <b>{game.code}</b>
            <span className={"ready-pill" + (game.status === "active" ? " ready" : "")}>
              {GAME_STATUS_LABELS[game.status]}
            </span>
            {game.is_member && <span className="note">you are in this game</span>}
          </div>
          <p className="note">
            {game.player_count} player{game.player_count === 1 ? "" : "s"}
            {game.player_names.length > 0 && <>: {game.player_names.join(", ")}</>}
            {game.creator_name && <> · opened by {game.creator_name}</>}
            {game.status === "active" && (
              <> · round {game.current_round}, {game.phase_name}</>
            )}
          </p>
          <div className="row">
            {game.is_member ? (
              <button
                className="primary"
                style={{ flex: 1 }}
                onClick={() => navigate(`/games/${game.code}`)}
              >
                {game.status === "lobby" ? "Back to lobby" : "Open"}
              </button>
            ) : game.can_join ? (
              <button
                className="primary"
                style={{ flex: 1 }}
                disabled={busy}
                onClick={() => joinGame(game.code)}
              >
                Join
              </button>
            ) : (
              <button style={{ flex: 1 }} disabled>
                {game.status === "lobby" ? "Full" : "In progress"}
              </button>
            )}
            {game.can_delete && (
              <button
                className="danger"
                style={{ flex: "0 0 auto" }}
                disabled={busy}
                onClick={() => deleteGame(game)}
              >
                Delete
              </button>
            )}
          </div>
        </div>
      ))}
    </>
  );
}
