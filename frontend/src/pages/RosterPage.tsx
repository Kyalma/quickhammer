import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Unit } from "../api/types";
import { UnitCard } from "../components/UnitCard";

const NO_FACTION = "Unaligned";

function groupByFaction(units: Unit[]): [string, Unit[]][] {
  const groups = new Map<string, Unit[]>();
  for (const unit of units) {
    const key = unit.faction.trim() || NO_FACTION;
    const list = groups.get(key) ?? [];
    list.push(unit);
    groups.set(key, list);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

export function RosterPage() {
  const navigate = useNavigate();
  const [units, setUnits] = useState<Unit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Unit[]>("/api/units")
      .then(setUnits)
      .catch((err) => setError(err.message));
  }, []);

  const factions = useMemo(() => groupByFaction(units ?? []), [units]);
  const grandTotal = useMemo(
    () => (units ?? []).reduce((sum, u) => sum + u.points, 0),
    [units],
  );

  return (
    <>
      <div className="row" style={{ alignItems: "center", marginBottom: "1rem" }}>
        <h1 style={{ flex: 1 }}>My roster</h1>
        <button className="primary" style={{ flex: "0 0 auto" }} onClick={() => navigate("/library")}>
          + From library
        </button>
        <button style={{ flex: "0 0 auto" }} onClick={() => navigate("/units/new")}>
          + New unit
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {units && units.length === 0 && (
        <p className="note">No units yet. Create your first unit to get started.</p>
      )}

      {factions.map(([faction, factionUnits]) => {
        const total = factionUnits.reduce((sum, u) => sum + u.points, 0);
        return (
          <section key={faction} style={{ marginBottom: "1.5rem" }}>
            <div className="faction-header">
              <h2>{faction}</h2>
              <span className="note">
                {factionUnits.length} unit{factionUnits.length > 1 ? "s" : ""}
                {total > 0 && <> · <b>{total} pts</b></>}
              </span>
            </div>
            <div className="grid">
              {factionUnits.map((unit) => (
                <UnitCard key={unit.id} unit={unit} onClick={() => navigate(`/units/${unit.id}`)} />
              ))}
            </div>
          </section>
        );
      })}

      {factions.length > 1 && grandTotal > 0 && (
        <p className="note" style={{ textAlign: "right" }}>
          Roster total: <b>{grandTotal} pts</b>
        </p>
      )}
    </>
  );
}
