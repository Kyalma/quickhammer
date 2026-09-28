import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { factionLabel, PHASES, type Game } from "../api/types";
import { ArmySelector } from "../components/ArmySelector";
import { PhaseTracker } from "../components/PhaseTracker";
import { useAuth } from "../context/AuthContext";
import { usePolling } from "../hooks/usePolling";

const POLL_MS = 2500;

export function GamePage() {
  const { code } = useParams();
  const { player } = useAuth();
  const [game, setGame] = useState<Game | null>(null);
  const [error, setError] = useState<string | null>(null);

  usePolling(
    () => {
      api.get<Game>(`/api/games/${code}`).then(setGame).catch((e) => setError(e.message));
    },
    POLL_MS,
    game?.status !== "finished",
  );

  if (error) return <p className="error">{error}</p>;
  if (!game || !player) return <p className="note">Loading game…</p>;

  const me = game.players.find((gp) => gp.player.id === player.id);
  const isMyTurn = game.active_player_id === player.id;
  const activePlayer = game.players.find((gp) => gp.player.id === game.active_player_id);
  const phaseName = PHASES[game.current_phase];
  const combatPhase = phaseName === "Shooting" || phaseName === "Fight";

  async function act(path: string) {
    setError(null);
    try {
      const updated = await api.post<Game>(`/api/games/${code}/${path}`);
      setGame(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    }
  }

  // --- Lobby view ---------------------------------------------------------
  if (game.status === "lobby") {
    return (
      <>
        <h1>Waiting for players</h1>
        <div className="card" style={{ textAlign: "center" }}>
          <p className="note">Share this code with your opponents:</p>
          <span className="code-badge">{game.code}</span>
        </div>
        <div className="card">
          {game.players.map((gp) => (
            <p key={gp.player.id}>
              {gp.player.name}{" "}
              <span className={"ready-pill" + (gp.is_ready ? " ready" : "")}>
                {gp.is_ready ? "Ready" : "Not ready"}
              </span>
              {gp.army.length > 0 && (
                <span className="note">
                  {" "}
                  — {factionLabel(gp.faction)}, {gp.army.length} unit
                  {gp.army.length === 1 ? "" : "s"}
                  {gp.army_points > 0 && <> · {gp.army_points} pts</>}
                </span>
              )}
            </p>
          ))}
          {game.players.length < 2 && (
            <p className="note">At least two players are needed to start.</p>
          )}
        </div>

        {me && <ArmySelector code={game.code} me={me} onSaved={setGame} />}

        <button
          className="primary"
          onClick={() => act("ready")}
          style={{ width: "100%" }}
          disabled={!me?.is_ready && (me?.army.length ?? 0) === 0}
        >
          {me?.is_ready ? "Cancel ready" : "I'm ready"}
        </button>
        {!me?.is_ready && (me?.army.length ?? 0) === 0 && (
          <p className="note" style={{ textAlign: "center" }}>
            Confirm your army before readying up.
          </p>
        )}
      </>
    );
  }

  // --- Finished view --------------------------------------------------------
  if (game.status === "finished") {
    return (
      <>
        <h1>Game over</h1>
        <p>
          This match has ended. <Link to="/lobby">Back to the lobby</Link>
        </p>
      </>
    );
  }

  // --- Active game ----------------------------------------------------------
  return (
    <>
      <div className="row" style={{ alignItems: "center" }}>
        <h1 style={{ flex: 1 }}>Round {game.current_round}</h1>
        <span className="note" style={{ flex: "0 0 auto" }}>
          Game {game.code}
        </span>
      </div>
      <p>
        {isMyTurn ? (
          <b>Your turn</b>
        ) : (
          <>Waiting for <b>{activePlayer?.player.name ?? "…"}</b></>
        )}{" "}
        — {phaseName} Phase
      </p>
      <PhaseTracker current={game.current_phase} />

      {combatPhase && (
        <Link to={`/games/${game.code}/combat`}>
          <button className="primary" style={{ width: "100%", marginBottom: "1rem" }}>
            ⚔ Resolve an attack
          </button>
        </Link>
      )}

      {isMyTurn && (
        <button onClick={() => act("advance")} style={{ width: "100%" }}>
          {game.current_phase === PHASES.length - 1 ? "End my turn" : `Next phase →`}
        </button>
      )}

      <div className="card" style={{ marginTop: "1rem" }}>
        <h2>Players</h2>
        {game.players.map((gp) => (
          <p key={gp.player.id}>
            {gp.player.name}
            {gp.player.id === game.active_player_id && " ← active"}
            <span className="note">
              {" "}
              — {factionLabel(gp.faction)}, {gp.army.length} unit
              {gp.army.length === 1 ? "" : "s"}
              {gp.army_points > 0 && <> · {gp.army_points} pts</>}
            </span>
          </p>
        ))}
        <button className="danger" onClick={() => act("finish")} style={{ marginTop: "0.5rem" }}>
          End game
        </button>
      </div>
    </>
  );
}
