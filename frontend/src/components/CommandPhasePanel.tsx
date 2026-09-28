import { useState } from "react";
import { api } from "../api/client";
import type { ArmyUnitSummary, BattleShockResult, Game, GamePlayer } from "../api/types";

/**
 * The 10th-edition Command phase: gain a Command Point, then take a
 * Battle-shock test for every unit below half strength. The app never rolls;
 * the player enters the 2D6 total they rolled on the table.
 */
export function CommandPhasePanel({
  code,
  me,
  onChange,
}: {
  code: string;
  me: GamePlayer;
  onChange: (game: Game) => void;
}) {
  const [rolls, setRolls] = useState<Record<number, string>>({});
  const [outcomes, setOutcomes] = useState<Record<number, BattleShockResult>>({});
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pending = me.army.filter((u) => u.needs_shock_test);
  const shocked = me.army.filter((u) => u.is_battle_shocked && !u.is_destroyed);

  async function test(unit: ArmyUnitSummary) {
    const roll = Number(rolls[unit.id]);
    if (!Number.isInteger(roll) || roll < 2 || roll > 12) {
      setError("Enter the 2D6 total you rolled, from 2 to 12.");
      return;
    }
    setBusyId(unit.id);
    setError(null);
    try {
      const result = await api.post<BattleShockResult>(
        `/api/games/${code}/units/${unit.id}/battle-shock`,
        { roll },
      );
      setOutcomes((prev) => ({ ...prev, [unit.id]: result }));
      onChange(result.game);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not resolve the test");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="card">
      <h2>Command phase</h2>
      <p className="result-summary">
        Command points: <b>{me.command_points}</b>
      </p>

      <h3>Battle-shock</h3>
      {pending.length === 0 && shocked.length === 0 && (
        <p className="note">
          No unit is below half strength, so no Battle-shock tests are needed.
        </p>
      )}

      {pending.map((unit) => {
        const outcome = outcomes[unit.id];
        return (
          <div key={unit.id} className="unit-state">
            <div className="unit-state-head">
              <b>{unit.name}</b>
              <span className="note">
                {unit.models_remaining} / {unit.model_count} models · Ld {unit.leadership}+
              </span>
            </div>
            {outcome ? (
              <p className={outcome.passed ? "note" : "error"}>
                Rolled {outcome.roll} against Ld {outcome.leadership}+:{" "}
                {outcome.passed ? "passed" : "failed, unit is Battle-shocked"}
              </p>
            ) : (
              <div className="row" style={{ alignItems: "center" }}>
                <div className="field" style={{ flex: 1, marginBottom: 0 }}>
                  <label htmlFor={`roll-${unit.id}`}>Your 2D6 roll</label>
                  <input
                    id={`roll-${unit.id}`}
                    type="number"
                    inputMode="numeric"
                    min={2}
                    max={12}
                    value={rolls[unit.id] ?? ""}
                    onChange={(e) =>
                      setRolls((prev) => ({ ...prev, [unit.id]: e.target.value }))
                    }
                  />
                </div>
                <button
                  className="primary"
                  style={{ flex: "0 0 auto" }}
                  disabled={busyId === unit.id}
                  onClick={() => test(unit)}
                >
                  Test
                </button>
              </div>
            )}
          </div>
        );
      })}

      {error && <p className="error">{error}</p>}

      {shocked.length > 0 && (
        <>
          <p className="note" style={{ marginTop: "0.75rem" }}>
            Battle-shocked until the start of your next Command phase. Objective Control
            counts as 0, no Stratagems, and Desperate Escape tests when Falling Back.
          </p>
          {shocked.map((unit) => (
            <p key={unit.id}>
              {unit.name} <span className="ready-pill danger-pill">Battle-shocked</span>
            </p>
          ))}
        </>
      )}
    </div>
  );
}
