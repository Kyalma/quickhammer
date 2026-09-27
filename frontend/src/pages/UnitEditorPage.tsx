import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { emptyUnit, emptyWeapon, type Unit, type Weapon } from "../api/types";

function NumberField({
  label, value, onChange, min = 0, max = 99,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
}) {
  return (
    <div className="field">
      <label>{label}</label>
      <input
        type="number"
        inputMode="numeric"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

export function UnitEditorPage() {
  const { unitId } = useParams();
  const navigate = useNavigate();
  const isNew = unitId === "new";
  const [unit, setUnit] = useState<Unit>(emptyUnit());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isNew) {
      api.get<Unit>(`/api/units/${unitId}`).then(setUnit).catch((e) => setError(e.message));
    }
  }, [unitId, isNew]);

  function patch(partial: Partial<Unit>) {
    setUnit((u) => ({ ...u, ...partial }));
  }

  function patchWeapon(index: number, partial: Partial<Weapon>) {
    setUnit((u) => ({
      ...u,
      weapons: u.weapons.map((w, i) => (i === index ? { ...w, ...partial } : w)),
    }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      // Clean up in-progress typing: trim keywords, drop empties.
      const payload: Unit = {
        ...unit,
        weapons: unit.weapons.map((w) => ({
          ...w,
          keywords: w.keywords.map((k) => k.trim()).filter(Boolean),
        })),
      };
      let saved: Unit;
      if (isNew) {
        saved = await api.post<Unit>("/api/units", payload);
      } else {
        saved = await api.put<Unit>(`/api/units/${unitId}`, payload);
      }
      // Upload the picture if one was chosen.
      const file = fileInput.current?.files?.[0];
      if (file) {
        saved = await api.upload<Unit>(`/api/units/${saved.id}/image`, file);
      }
      navigate("/roster");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete ${unit.name || "this unit"}?`)) return;
    await api.delete(`/api/units/${unitId}`);
    navigate("/roster");
  }

  return (
    <form onSubmit={save}>
      <h1>{isNew ? "New unit" : `Edit ${unit.name}`}</h1>
      {error && <p className="error">{error}</p>}

      <div className="card">
        <div className="field">
          <label>Unit name</label>
          <input
            value={unit.name}
            onChange={(e) => patch({ name: e.target.value })}
            required
            placeholder="e.g. Intercessor Squad"
          />
        </div>
        <div className="field">
          <label>Picture</label>
          {unit.image_path && (
            <img
              src={unit.image_path}
              alt={unit.name}
              style={{ width: 96, height: 96, objectFit: "cover", borderRadius: 10, display: "block", marginBottom: 8 }}
            />
          )}
          <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp,image/gif" />
        </div>
        <h2>Statline</h2>
        <div className="row">
          <NumberField label='Movement (")' value={unit.movement} onChange={(v) => patch({ movement: v })} max={30} />
          <NumberField label="Toughness" value={unit.toughness} onChange={(v) => patch({ toughness: v })} min={1} max={16} />
          <NumberField label="Save (X+)" value={unit.save} onChange={(v) => patch({ save: v })} min={2} max={7} />
        </div>
        <div className="row">
          <div className="field">
            <label>Invulnerable save (X++, blank = none)</label>
            <input
              type="number"
              inputMode="numeric"
              min={2}
              max={6}
              value={unit.invuln_save ?? ""}
              onChange={(e) =>
                patch({ invuln_save: e.target.value === "" ? null : Number(e.target.value) })
              }
            />
          </div>
          <NumberField label="Wounds / model" value={unit.wounds} onChange={(v) => patch({ wounds: v })} min={1} max={40} />
          <NumberField label="Models" value={unit.model_count} onChange={(v) => patch({ model_count: v })} min={1} max={30} />
        </div>
        <div className="row">
          <NumberField label="Leadership" value={unit.leadership} onChange={(v) => patch({ leadership: v })} min={4} max={10} />
          <NumberField label="OC" value={unit.oc} onChange={(v) => patch({ oc: v })} max={10} />
        </div>
      </div>

      <h2>Weapons</h2>
      {unit.weapons.map((weapon, index) => (
        <div className="card" key={index}>
          <div className="row">
            <div className="field" style={{ flex: 2 }}>
              <label>Weapon name</label>
              <input
                value={weapon.name}
                onChange={(e) => patchWeapon(index, { name: e.target.value })}
                required
                placeholder="e.g. Bolt rifle"
              />
            </div>
            <div className="field">
              <label>Type</label>
              <select
                value={weapon.kind}
                onChange={(e) => patchWeapon(index, { kind: e.target.value as Weapon["kind"] })}
              >
                <option value="ranged">Ranged</option>
                <option value="melee">Melee</option>
              </select>
            </div>
          </div>
          <div className="row">
            <NumberField label='Range (")' value={weapon.range} onChange={(v) => patchWeapon(index, { range: v })} max={120} />
            <div className="field">
              <label>Attacks (e.g. 2, D6, D6+1)</label>
              <input
                value={weapon.attacks}
                onChange={(e) => patchWeapon(index, { attacks: e.target.value })}
                placeholder="D6+1"
                required
              />
            </div>
            <NumberField
              label={weapon.kind === "ranged" ? "BS (X+)" : "WS (X+)"}
              value={weapon.skill}
              onChange={(v) => patchWeapon(index, { skill: v })}
              min={2}
              max={6}
            />
          </div>
          <div className="row">
            <NumberField label="Strength" value={weapon.strength} onChange={(v) => patchWeapon(index, { strength: v })} min={1} max={24} />
            <div className="field">
              <label>AP (0 to -6)</label>
              <input
                type="number"
                inputMode="numeric"
                min={-6}
                max={0}
                value={weapon.ap === 0 ? 0 : -weapon.ap}
                onChange={(e) =>
                  // Displayed in 40k notation (-2); stored as a positive number.
                  patchWeapon(index, { ap: Math.min(6, Math.abs(Number(e.target.value))) })
                }
              />
            </div>
            <div className="field">
              <label>Damage (e.g. 1, D3, D6+2)</label>
              <input
                value={weapon.damage}
                onChange={(e) => patchWeapon(index, { damage: e.target.value })}
                placeholder="D3"
                required
              />
            </div>
          </div>
          <div className="field">
            <label>Keywords (comma-separated: SUSTAINED HITS 1, LETHAL HITS)</label>
            <input
              value={weapon.keywords.join(",")}
              onChange={(e) =>
                // Split without trimming so a trailing comma survives while
                // typing; keywords are cleaned up on save.
                patchWeapon(index, { keywords: e.target.value.split(",") })
              }
            />
          </div>
          <button
            type="button"
            className="danger"
            onClick={() =>
              setUnit((u) => ({ ...u, weapons: u.weapons.filter((_, i) => i !== index) }))
            }
          >
            Remove weapon
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => setUnit((u) => ({ ...u, weapons: [...u.weapons, emptyWeapon()] }))}
        style={{ marginBottom: "1rem" }}
      >
        + Add weapon
      </button>

      <div className="row">
        <button className="primary" type="submit" disabled={busy}>
          {busy ? "Saving…" : "Save unit"}
        </button>
        {!isNew && (
          <button type="button" className="danger" onClick={remove}>
            Delete unit
          </button>
        )}
      </div>
    </form>
  );
}
