import { useState } from "react";
import { api } from "../api/client";
import type { ArmyUnitSummary, Game, GamePlayer } from "../api/types";

/**
 * Your army's live condition during a game, with controls to record casualties.
 * Players update their own units, the same way you remove your own models at
 * the table.
 */
export function ArmyStatusPanel({
  code,
  me,
  onChange,
}: {
  code: string;
  me: GamePlayer;
  onChange: (game: Game) => void;
}) {
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function applyWounds(unit: ArmyUnitSummary, wounds: number) {
    setBusyId(unit.id);
    setError(null);
    try {
      onChange(
        await api.post<Game>(`/api/games/${code}/units/${unit.id}/damage`, { wounds }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update that unit");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="card">
      <h2>Your army</h2>
      {error && <p className="error">{error}</p>}
      {me.army.map((unit) => (
        <div key={unit.id} className="unit-state">
          <div className="unit-state-head">
            <b className={unit.is_destroyed ? "struck" : undefined}>{unit.name}</b>
            {unit.is_destroyed && <span className="ready-pill danger-pill">Destroyed</span>}
            {unit.is_battle_shocked && !unit.is_destroyed && (
              <span className="ready-pill danger-pill">Battle-shocked</span>
            )}
            {unit.below_half_strength && !unit.is_destroyed && !unit.is_battle_shocked && (
              <span className="ready-pill">Below half</span>
            )}
          </div>
          <div className="row" style={{ alignItems: "center" }}>
            <span style={{ flex: 1 }} className="note">
              {unit.models_remaining} / {unit.model_count} model
              {unit.model_count === 1 ? "" : "s"}
              {unit.wounds > 1 && unit.wounds_lost > 0 && (
                <>
                  {" "}
                  · lead model on {unit.wounds - unit.wounds_lost} / {unit.wounds} wounds
                </>
              )}
            </span>
            <button
              style={{ flex: "0 0 auto" }}
              disabled={busyId === unit.id}
              onClick={() => applyWounds(unit, -1)}
              title="Undo one wound"
            >
              + 1 W
            </button>
            <button
              style={{ flex: "0 0 auto" }}
              disabled={busyId === unit.id || unit.is_destroyed}
              onClick={() => applyWounds(unit, 1)}
              title="Record one wound"
            >
              − 1 W
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
