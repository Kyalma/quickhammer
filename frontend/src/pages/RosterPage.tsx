import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Unit } from "../api/types";
import { UnitCard } from "../components/UnitCard";

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
      <div className="grid">
        {units?.map((unit) => (
          <UnitCard key={unit.id} unit={unit} onClick={() => navigate(`/units/${unit.id}`)} />
        ))}
      </div>
    </>
  );
}
