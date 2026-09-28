import type { Unit } from "../api/types";

export function UnitCard({ unit, onClick }: { unit: Unit; onClick?: () => void }) {
  return (
    <div
      className="card unit-card"
      onClick={onClick}
      style={onClick ? { cursor: "pointer" } : undefined}
    >
      {unit.image_path ? (
        <img src={unit.image_path} alt={unit.name} />
      ) : (
        <div className="placeholder">⚔</div>
      )}
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
          <h2>{unit.name}</h2>
          {unit.points > 0 && <span className="points-badge">{unit.points} pts</span>}
        </div>
        <div className="statline">
          <span>M <b>{unit.movement}"</b></span>
          <span>T <b>{unit.toughness}</b></span>
          <span>Sv <b>{unit.save}+</b></span>
          {unit.invuln_save != null && <span>Inv <b>{unit.invuln_save}++</b></span>}
          <span>W <b>{unit.wounds}</b></span>
          <span>OC <b>{unit.oc}</b></span>
          <span>Models <b>{unit.model_count}</b></span>
        </div>
        <p className="note">
          {unit.weapons.length > 0
            ? unit.weapons.map((w) => w.name).join(", ")
            : "No weapons yet"}
        </p>
      </div>
    </div>
  );
}
