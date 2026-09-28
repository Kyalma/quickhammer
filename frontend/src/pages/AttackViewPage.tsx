import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { AttackRoll } from "../api/types";
import { DiceRollTrack } from "../components/DiceRollTrack";

/** Read-only view of an attack, so the defending player sees the same dice. */
export function AttackViewPage() {
  const { code, rollId } = useParams();
  const [roll, setRoll] = useState<AttackRoll | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<AttackRoll>(`/api/games/${code}/shooting/${rollId}`)
      .then(setRoll)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load that attack"),
      );
  }, [code, rollId]);

  return (
    <>
      <div className="row" style={{ alignItems: "center" }}>
        <h1 style={{ flex: 1 }}>
          {roll ? `${roll.attacker_name} → ${roll.target_name}` : "Attack"}
        </h1>
        <Link to={`/games/${code}`} style={{ flex: "0 0 auto" }}>
          ← Back to game
        </Link>
      </div>
      {error && <p className="error">{error}</p>}
      {!roll && !error && <p className="note">Loading the dice…</p>}
      {roll && (
        <>
          <DiceRollTrack rolls={roll.rolls} />
          <p className="note">
            {roll.resolved
              ? roll.applied
                ? "This result has been applied."
                : "This result was discarded."
              : "Waiting for your opponent to confirm."}
          </p>
        </>
      )}
    </>
  );
}
