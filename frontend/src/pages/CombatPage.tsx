import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import {
  ignoresPistolRule,
  isPistol,
  type ArmyUnitSummary,
  type AttackRoll,
  type CombatResult,
  type Game,
  type GameArmy,
  type Unit,
} from "../api/types";
import { DiceMathBreakdown } from "../components/DiceMathBreakdown";
import { DiceRollTrack } from "../components/DiceRollTrack";
import { useAuth } from "../context/AuthContext";

/**
 * Shooting: pick a unit and a target, choose which weapons fire, roll, look at
 * the dice, then confirm to apply the damage.
 */
export function CombatPage() {
  const { code } = useParams();
  const { player } = useAuth();
  const navigate = useNavigate();

  const [myUnits, setMyUnits] = useState<Unit[]>([]);
  const [enemyUnits, setEnemyUnits] = useState<Unit[]>([]);
  const [state, setState] = useState<Map<number, ArmyUnitSummary>>(new Map());
  const [attackerId, setAttackerId] = useState<number | "">("");
  const [defenderId, setDefenderId] = useState<number | "">("");
  const [weaponIds, setWeaponIds] = useState<Set<number>>(new Set());
  const [preview, setPreview] = useState<CombatResult[] | null>(null);
  const [roll, setRoll] = useState<AttackRoll | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Which phase we are in decides melee vs ranged, and whether dice can roll.
  const [phase, setPhase] = useState<string>("");

  useEffect(() => {
    if (!player) return;
    Promise.all([
      api.get<GameArmy[]>(`/api/games/${code}/armies`),
      api.get<Game>(`/api/games/${code}`),
    ])
      .then(([armies, game]) => {
        setMyUnits(armies.find((a) => a.player.id === player.id)?.units ?? []);
        setEnemyUnits(
          armies.filter((a) => a.player.id !== player.id).flatMap((a) => a.units),
        );
        setState(
          new Map(game.players.flatMap((gp) => gp.army.map((u) => [u.unit_id, u] as const))),
        );
        setPhase(game.phase_name);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load armies"),
      );
  }, [code, player]);

  // Rolled dice exist for shooting only; the Fight phase still uses the odds view.
  const isShooting = phase === "Shooting";
  const attacker = myUnits.find((u) => u.id === attackerId);
  const attackerState = attackerId === "" ? undefined : state.get(attackerId);
  const usableWeapons = useMemo(
    () =>
      (attacker?.weapons ?? []).filter((w) =>
        isShooting ? w.kind === "ranged" : w.kind === "melee",
      ),
    [attacker, isShooting],
  );
  const freeToMix = ignoresPistolRule(attacker);
  const chosen = usableWeapons.filter((w) => weaponIds.has(w.id!));
  // The Pistol either/or rule is a Shooting phase rule.
  const mixesPistols =
    isShooting && !freeToMix && chosen.some(isPistol) && chosen.some((w) => !isPistol(w));

  function condition(unitId: number | undefined): string {
    const unit = unitId === undefined ? undefined : state.get(unitId);
    if (!unit) return "";
    if (unit.is_destroyed) return " — destroyed";
    const parts: string[] = [];
    if (unit.models_remaining < unit.model_count) {
      parts.push(`${unit.models_remaining}/${unit.model_count} models`);
    }
    if (unit.is_battle_shocked) parts.push("Battle-shocked");
    if (unit.has_shot) parts.push("already shot");
    return parts.length > 0 ? ` — ${parts.join(", ")}` : "";
  }

  function pickAttacker(value: string) {
    setAttackerId(value === "" ? "" : Number(value));
    setWeaponIds(new Set());
    setPreview(null);
  }

  function toggleWeapon(id: number) {
    setPreview(null);
    setWeaponIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function showPreview() {
    setError(null);
    setBusy(true);
    try {
      // The odds endpoint takes one weapon, so ask per weapon and show each.
      const results = await Promise.all(
        chosen.map((w) =>
          api.post<CombatResult>("/api/combat/resolve", {
            attacker_unit_id: attackerId,
            weapon_id: w.id,
            defender_unit_id: defenderId,
          }),
        ),
      );
      setPreview(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not work out the odds");
    } finally {
      setBusy(false);
    }
  }

  async function rollAttack() {
    setError(null);
    setBusy(true);
    try {
      const attackerEntry = state.get(attackerId as number);
      const targetEntry = state.get(defenderId as number);
      const result = await api.post<AttackRoll>(`/api/games/${code}/shooting/resolve`, {
        attacker_game_unit_id: attackerEntry?.id,
        weapon_ids: [...weaponIds],
        target_game_unit_id: targetEntry?.id,
      });
      setRoll(result);
      setPreview(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not resolve the attack");
    } finally {
      setBusy(false);
    }
  }

  async function finish(action: "confirm" | "discard") {
    if (!roll) return;
    setError(null);
    setBusy(true);
    try {
      await api.post<Game>(`/api/games/${code}/shooting/${roll.id}/${action}`);
      navigate(`/games/${code}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not finish the attack");
      setBusy(false);
    }
  }

  // --- After rolling: dice, then confirm or discard ------------------------
  if (roll) {
    return (
      <>
        <h1>
          {roll.attacker_name} → {roll.target_name}
        </h1>
        {error && <p className="error">{error}</p>}
        <DiceRollTrack rolls={roll.rolls} />
        <div className="row">
          <button
            className="primary"
            style={{ flex: 2 }}
            disabled={busy}
            onClick={() => finish("confirm")}
          >
            {busy ? "Applying…" : "Confirm and apply"}
          </button>
          <button
            className="danger"
            style={{ flex: 1 }}
            disabled={busy}
            onClick={() => finish("discard")}
            title="Throw this result away and give the unit its shot back."
          >
            Discard
          </button>
        </div>
      </>
    );
  }

  const ready =
    attackerId !== "" && defenderId !== "" && chosen.length > 0 && !mixesPistols;

  return (
    <>
      <div className="row" style={{ alignItems: "center" }}>
        <h1 style={{ flex: 1 }}>{isShooting ? "Shoot" : "Fight"}</h1>
        <Link to={`/games/${code}`} style={{ flex: "0 0 auto" }}>
          ← Back to game
        </Link>
      </div>
      {!isShooting && (
        <p className="note">
          Rolled dice are only built for the Shooting phase so far. Work out the odds here, then
          record the casualties yourself in the <b>Your army</b> panel.
        </p>
      )}
      {error && <p className="error">{error}</p>}

      <div className="versus">
        <div className="card">
          <h2>Attacker (you)</h2>
          <div className="field">
            <label>Unit</label>
            <select value={attackerId} onChange={(e) => pickAttacker(e.target.value)}>
              <option value="">Choose a unit…</option>
              {myUnits.map((u) => (
                <option
                  key={u.id}
                  value={u.id}
                  disabled={state.get(u.id!)?.is_destroyed || state.get(u.id!)?.has_shot}
                >
                  {u.name}
                  {condition(u.id)}
                </option>
              ))}
            </select>
          </div>

          {attacker && (
            <fieldset className="pick-group">
              <legend>{isShooting ? "Weapons firing" : "Melee weapons"}</legend>
              {usableWeapons.length === 0 && (
                <p className="note">
                  This unit has no {isShooting ? "ranged" : "melee"} weapons.
                </p>
              )}
              {usableWeapons.map((w) => (
                <label key={w.id} className="pick-row">
                  <input
                    type="checkbox"
                    checked={weaponIds.has(w.id!)}
                    onChange={() => toggleWeapon(w.id!)}
                  />
                  <span>
                    {w.name}
                    {isPistol(w) && <span className="ready-pill"> Pistol</span>}
                    <span className="note">
                      {" "}
                      S{w.strength} AP{w.ap === 0 ? "0" : `-${w.ap}`} D{w.damage} ·{" "}
                      {w.attacks} attacks ·{" "}
                      {w.carrier_count === 0
                        ? "all models"
                        : `${w.carrier_count} model${w.carrier_count === 1 ? "" : "s"}`}
                    </span>
                  </span>
                </label>
              ))}
              {isShooting && (
                <p className="note">
                  {freeToMix
                    ? "Monsters and Vehicles may fire pistols alongside everything else."
                    : "A model fires either its pistols or its other weapons, never both."}
                </p>
              )}
            </fieldset>
          )}
          {mixesPistols && (
            <p className="error">
              Pistols cannot be fired together with other weapons.
            </p>
          )}
          {attackerState?.has_shot && (
            <p className="error">This unit has already shot this phase.</p>
          )}
        </div>

        <div className="vs-label">VS</div>

        <div className="card">
          <h2>Target</h2>
          <div className="field">
            <label>Enemy unit</label>
            <select
              value={defenderId}
              onChange={(e) => {
                setDefenderId(e.target.value === "" ? "" : Number(e.target.value));
                setPreview(null);
              }}
            >
              <option value="">Choose a target…</option>
              {enemyUnits.map((u) => (
                <option key={u.id} value={u.id} disabled={state.get(u.id!)?.is_destroyed}>
                  {u.name} (T{u.toughness} Sv{u.save}+ W{u.wounds}x{u.model_count})
                  {condition(u.id)}
                </option>
              ))}
            </select>
          </div>
          {enemyUnits.length === 0 && (
            <p className="note">No opposing units have been fielded in this game.</p>
          )}
        </div>
      </div>

      <div className="row" style={{ margin: "1rem 0" }}>
        <button
          className={isShooting ? undefined : "primary"}
          style={{ flex: 1 }}
          disabled={busy || !ready}
          onClick={showPreview}
        >
          {isShooting ? "Preview odds" : "Work out the odds"}
        </button>
        {isShooting && (
          <button className="primary" style={{ flex: 2 }} disabled={busy || !ready} onClick={rollAttack}>
            {busy ? "Rolling…" : "🎲 Roll to hit"}
          </button>
        )}
      </div>

      {preview?.map((result, i) => (
        <DiceMathBreakdown key={i} result={result} />
      ))}
    </>
  );
}
