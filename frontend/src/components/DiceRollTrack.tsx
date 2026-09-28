import { useEffect, useState } from "react";
import type { RolledDie, ShootingRolls } from "../api/types";

const STAGE_REVEAL_MS = 550;

/** Maps an outcome label to a colour class. Unknown labels stay neutral. */
function dieClass(outcome: string): string {
  const text = outcome.toLowerCase();
  if (text.includes("critical")) return "die crit";
  if (text.startsWith("miss") || text.startsWith("no wound")) return "die fail";
  if (text.includes("save failed") || text.includes("no save")) return "die good";
  if (text.startsWith("saved")) return "die fail";
  if (text.startsWith("hit") || text.startsWith("wounded")) return "die good";
  if (text.startsWith("auto") || text.startsWith("sustained")) return "die auto";
  if (text.includes("damage")) return "die good";
  return "die";
}

function Die({ die }: { die: RolledDie }) {
  // A value of 0 means no die was physically rolled (auto-hit, auto-wound,
  // sustained hit, or no save possible).
  return (
    <span className={dieClass(die.outcome)} title={die.outcome}>
      {die.value > 0 ? die.value : "—"}
    </span>
  );
}

/** Distinct outcomes in this stage with counts, e.g. "6 Hit · 4 Miss". */
function outcomeTally(dice: RolledDie[]): string {
  const counts = new Map<string, number>();
  for (const die of dice) counts.set(die.outcome, (counts.get(die.outcome) ?? 0) + 1);
  return [...counts.entries()]
    .filter(([label]) => !label.includes("damage") && !label.includes("attacks"))
    .map(([label, n]) => `${n} ${label}`)
    .join(" · ");
}

export function DiceRollTrack({ rolls }: { rolls: ShootingRolls }) {
  // Reveal stages one at a time: this is most of what makes it feel like
  // rolling rather than reading a table.
  const totalStages = rolls.weapons.reduce((n, w) => n + w.stages.length, 0);
  const [revealed, setRevealed] = useState(1);

  useEffect(() => {
    setRevealed(1);
  }, [rolls]);

  useEffect(() => {
    if (revealed >= totalStages) return;
    const timer = window.setTimeout(() => setRevealed((n) => n + 1), STAGE_REVEAL_MS);
    return () => window.clearTimeout(timer);
  }, [revealed, totalStages]);

  const done = revealed >= totalStages;
  let index = 0;

  return (
    <>
      {rolls.weapons.map((weapon) => (
        <div className="card" key={weapon.weapon}>
          <div className="unit-state-head">
            <b>{weapon.weapon}</b>
            <span className="note">
              {weapon.models_firing} model{weapon.models_firing === 1 ? "" : "s"} firing
            </span>
          </div>
          {weapon.stages.map((stage) => {
            const visible = index++ < revealed;
            if (!visible) return null;
            const tally = outcomeTally(stage.dice);
            return (
              <div className="roll-stage" key={stage.name}>
                <div className="roll-stage-head">
                  <b>{stage.name}</b>
                  {tally && <span className="note">{tally}</span>}
                </div>
                {stage.dice.length > 0 ? (
                  <div className="dice-tray">
                    {stage.dice.map((die, i) => (
                      <Die key={i} die={die} />
                    ))}
                  </div>
                ) : (
                  <p className="note">No dice</p>
                )}
                <p className="note">{stage.summary}</p>
              </div>
            );
          })}
        </div>
      ))}

      {done && (
        <div className="card">
          <h2>{rolls.outcome}</h2>
          {rolls.allocation.map((line, i) => (
            <p key={i} className="note">
              {line}
            </p>
          ))}
          <p className="result-summary">
            <b>{rolls.total_damage}</b> damage ·{" "}
            <b>{rolls.models_slain}</b> model{rolls.models_slain === 1 ? "" : "s"} slain
          </p>
          {rolls.notes.map((note) => (
            <p key={note} className="note">
              ℹ {note}
            </p>
          ))}
        </div>
      )}
    </>
  );
}
