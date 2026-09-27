import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Game } from "../api/types";

export function LobbyPage() {
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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

  async function joinGame(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const game = await api.post<Game>(`/api/games/${code.trim().toUpperCase()}/join`);
      navigate(`/games/${game.code}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not join game");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Play</h1>
      {error && <p className="error">{error}</p>}
      <div className="grid">
        <div className="card">
          <h2>Host a game</h2>
          <p className="note">Create a match and share the join code with your opponents.</p>
          <button className="primary" onClick={createGame} disabled={busy} style={{ marginTop: "0.5rem" }}>
            Create game
          </button>
        </div>
        <div className="card">
          <h2>Join a game</h2>
          <form onSubmit={joinGame}>
            <div className="field">
              <label>Join code</label>
              <input
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="e.g. K7X2P"
                maxLength={8}
                required
                style={{ textTransform: "uppercase", letterSpacing: "0.2em" }}
              />
            </div>
            <button className="primary" type="submit" disabled={busy}>
              Join
            </button>
          </form>
        </div>
      </div>
    </>
  );
}
