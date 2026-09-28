import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { factionLabel, type Game, type GamePlayer, type Unit } from "../api/types";

/**
 * Lobby army picker: one faction (radio), then one or more of its units
 * (checkboxes). Saving replaces the player's selection for this game.
 */
export function ArmySelector({
  code,
  me,
  onSaved,
}: {
  code: string;
  me: GamePlayer;
  onSaved: (game: Game) => void;
}) {
  const [units, setUnits] = useState<Unit[] | null>(null);
  const [faction, setFaction] = useState<string | null>(
    me.army.length > 0 ? me.faction : null,
  );
  const [selected, setSelected] = useState<Set<number>>(
    () => new Set(me.army.map((u) => u.id)),
  );
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get<Unit[]>("/api/units").then(setUnits).catch((e) => setError(e.message));
  }, []);

  // Units grouped by faction, alphabetically.
  const byFaction = useMemo(() => {
    const groups = new Map<string, Unit[]>();
    for (const unit of units ?? []) {
      const key = unit.faction.trim();
      groups.set(key, [...(groups.get(key) ?? []), unit]);
    }
    return [...groups.entries()].sort(([a], [b]) =>
      factionLabel(a).localeCompare(factionLabel(b)),
    );
  }, [units]);

  const factionUnits = byFaction.find(([f]) => f === faction)?.[1] ?? [];
  const selectedUnits = factionUnits.filter((u) => selected.has(u.id!));
  const totalPoints = selectedUnits.reduce((sum, u) => sum + u.points, 0);
  const allSelected = factionUnits.length > 0 && selectedUnits.length === factionUnits.length;

  function chooseFaction(next: string) {
    setFaction(next);
    // Default to the whole faction; the player can uncheck from there.
    const unitsOfFaction = byFaction.find(([f]) => f === next)?.[1] ?? [];
    setSelected(new Set(unitsOfFaction.map((u) => u.id!)));
  }

  function toggleUnit(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function save() {
    setError(null);
    setSaving(true);
    try {
      const game = await api.post<Game>(`/api/games/${code}/army`, {
        unit_ids: [...selected],
      });
      onSaved(game);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your army");
    } finally {
      setSaving(false);
    }
  }

  if (error && !units) return <p className="error">{error}</p>;
  if (!units) return <p className="note">Loading your roster…</p>;

  if (units.length === 0) {
    return (
      <div className="card">
        <h2>Your army</h2>
        <p className="note">
          Your roster is empty. Add units in Roster before joining a game.
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>Your army</h2>
      <p className="note">Pick one faction, then the units you are fielding.</p>

      <fieldset className="pick-group">
        <legend>Faction</legend>
        {byFaction.map(([value, factionsUnits]) => (
          <label key={value} className="pick-row">
            <input
              type="radio"
              name="faction"
              checked={faction === value}
              onChange={() => chooseFaction(value)}
            />
            <span>
              {factionLabel(value)}{" "}
              <span className="note">
                ({factionsUnits.length} unit{factionsUnits.length > 1 ? "s" : ""})
              </span>
            </span>
          </label>
        ))}
      </fieldset>

      {faction !== null && (
        <fieldset className="pick-group">
          <legend>
            Units{" "}
            <button
              type="button"
              className="link-button"
              onClick={() =>
                setSelected(allSelected ? new Set() : new Set(factionUnits.map((u) => u.id!)))
              }
            >
              {allSelected ? "clear all" : "select all"}
            </button>
          </legend>
          {factionUnits.map((unit) => (
            <label key={unit.id} className="pick-row">
              <input
                type="checkbox"
                checked={selected.has(unit.id!)}
                onChange={() => toggleUnit(unit.id!)}
              />
              <span>
                {unit.name}
                {unit.points > 0 && <span className="note"> · {unit.points} pts</span>}
              </span>
            </label>
          ))}
        </fieldset>
      )}

      {error && <p className="error">{error}</p>}

      <div className="row" style={{ alignItems: "center" }}>
        <span style={{ flex: 1 }}>
          {selectedUnits.length} unit{selectedUnits.length === 1 ? "" : "s"}
          {totalPoints > 0 && <> · <b>{totalPoints} pts</b></>}
        </span>
        <button
          className="primary"
          style={{ flex: "0 0 auto" }}
          disabled={saving || selectedUnits.length === 0}
          onClick={save}
        >
          {saving ? "Saving…" : "Confirm army"}
        </button>
      </div>
    </div>
  );
}
