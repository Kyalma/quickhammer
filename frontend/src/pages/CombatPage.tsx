import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { CombatResult, Game, Unit } from "../api/types";
import { DiceMathBreakdown } from "../components/DiceMathBreakdown";
import { useAuth } from "../context/AuthContext";

export function CombatPage() {
  const { code } = useParams();
  const { player } = useAuth();
  const [myUnits, setMyUnits] = useState<Unit[]>([]);
  const [enemyUnits, setEnemyUnits] = useState<Unit[]>([]);
  const [attackerId, setAttackerId] = useState<number | "">("");
  const [weaponId, setWeaponId] = useState<number | "">("");
  const [defenderId, setDefenderId] = useState<number | "">("");
  const [result, setResult] = useState<CombatResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Load my roster and every opponent's roster.
  useEffect(() => {
    if (!player) return;
    (async () => {
      try {
        const [mine, game] = await Promise.all([
          api.get<Unit[]>("/api/units"),
          api.get<Game>(`/api/games/${code}`),
        ]);
        setMyUnits(mine);
        const opponents = game.players.filter((gp) => gp.player.id !== player.id);
        const rosters = await Promise.all(
          opponents.map((gp) => api.get<Unit[]>(`/api/units/player/${gp.player.id}`)),
        );
        setEnemyUnits(rosters.flat());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load units");
      }
    })();
  }, [code, player]);

  const attacker = myUnits.find((u) => u.id === attackerId);

  async function resolve() {
    setError(null);
    setBusy(true);
    setResult(null);
    try {
      const res = await api.post<CombatResult>("/api/combat/resolve", {
        attacker_unit_id: attackerId,
        weapon_id: weaponId,
        defender_unit_id: defenderId,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not resolve combat");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="row" style={{ alignItems: "center" }}>
        <h1 style={{ flex: 1 }}>Resolve attack</h1>
        <Link to={`/games/${code}`} style={{ flex: "0 0 auto" }}>
          ← Back to game
        </Link>
      </div>
      {error && <p className="error">{error}</p>}

      <div className="versus">
        <div className="card">
          <h2>Attacker (you)</h2>
          <div className="field">
            <label>Unit</label>
            <select
              value={attackerId}
              onChange={(e) => {
                setAttackerId(e.target.value === "" ? "" : Number(e.target.value));
                setWeaponId("");
                setResult(null);
              }}
            >
              <option value="">Choose a unit…</option>
              {myUnits.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Weapon</label>
            <select
              value={weaponId}
              onChange={(e) => {
                setWeaponId(e.target.value === "" ? "" : Number(e.target.value));
                setResult(null);
              }}
              disabled={!attacker}
            >
              <option value="">Choose a weapon…</option>
              {attacker?.weapons.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.kind === "ranged" ? "ranged" : "melee"}, S{w.strength} AP{w.ap === 0 ? "0" : `-${w.ap}`} D{w.damage})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="vs-label">VS</div>

        <div className="card">
          <h2>Defender</h2>
          <div className="field">
            <label>Enemy unit</label>
            <select
              value={defenderId}
              onChange={(e) => {
                setDefenderId(e.target.value === "" ? "" : Number(e.target.value));
                setResult(null);
              }}
            >
              <option value="">Choose a target…</option>
              {enemyUnits.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name} (T{u.toughness} Sv{u.save}+ W{u.wounds}x{u.model_count})
                </option>
              ))}
            </select>
          </div>
          {enemyUnits.length === 0 && (
            <p className="note">Your opponents have no units in their roster yet.</p>
          )}
        </div>
      </div>

      <button
        className="primary"
        style={{ width: "100%", margin: "1rem 0" }}
        disabled={busy || attackerId === "" || weaponId === "" || defenderId === ""}
        onClick={resolve}
      >
        {busy ? "Rolling…" : "🎲 Resolve"}
      </button>

      {result && <DiceMathBreakdown result={result} />}
    </>
  );
}
