import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import FormControlLabel from "@mui/material/FormControlLabel";
import FormLabel from "@mui/material/FormLabel";
import Link from "@mui/material/Link";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink, useNavigate, useParams } from "react-router-dom";
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
        <Typography variant="h5" gutterBottom>
          {roll.attacker_name} → {roll.target_name}
        </Typography>
        {error && <Typography color="error">{error}</Typography>}
        <DiceRollTrack rolls={roll.rolls} />
        <Stack direction="row" spacing={1.5}>
          <Button
            variant="contained"
            sx={{ flex: 2 }}
            disabled={busy}
            onClick={() => finish("confirm")}
          >
            {busy ? "Applying…" : "Confirm and apply"}
          </Button>
          <Tooltip title="Throw this result away and give the unit its shot back.">
            <Box component="span" sx={{ flex: 1, display: "flex" }}>
              <Button
                color="error"
                fullWidth
                disabled={busy}
                onClick={() => finish("discard")}
              >
                Discard
              </Button>
            </Box>
          </Tooltip>
        </Stack>
      </>
    );
  }

  const ready =
    attackerId !== "" && defenderId !== "" && chosen.length > 0 && !mixesPistols;

  return (
    <>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 1 }}>
        <Typography variant="h5" sx={{ flexGrow: 1 }}>
          {isShooting ? "Shoot" : "Fight"}
        </Typography>
        <Link component={RouterLink} to={`/games/${code}`} sx={{ flexShrink: 0 }}>
          ← Back to game
        </Link>
      </Stack>
      {!isShooting && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Rolled dice are only built for the Shooting phase so far. Work out the odds here, then
          record the casualties yourself in the <b>Your army</b> panel.
        </Typography>
      )}
      {error && <Typography color="error">{error}</Typography>}

      <Box
        sx={{
          display: "grid",
          gap: 2,
          gridTemplateColumns: { xs: "1fr", md: "1fr auto 1fr" },
          alignItems: "start",
        }}
      >
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Attacker (you)
            </Typography>
            <TextField
              select
              label="Unit"
              value={attackerId}
              onChange={(e) => pickAttacker(e.target.value)}
              fullWidth
            >
              <MenuItem value="">Choose a unit…</MenuItem>
              {myUnits.map((u) => (
                <MenuItem
                  key={u.id}
                  value={u.id}
                  disabled={state.get(u.id!)?.is_destroyed || state.get(u.id!)?.has_shot}
                >
                  {u.name}
                  {condition(u.id)}
                </MenuItem>
              ))}
            </TextField>

            {attacker && (
              <Paper variant="outlined" sx={{ p: 1.5, mt: 1.5 }}>
                <FormLabel>{isShooting ? "Weapons firing" : "Melee weapons"}</FormLabel>
                {usableWeapons.length === 0 && (
                  <Typography variant="body2" color="text.secondary">
                    This unit has no {isShooting ? "ranged" : "melee"} weapons.
                  </Typography>
                )}
                <Stack>
                  {usableWeapons.map((w) => (
                    <FormControlLabel
                      key={w.id}
                      control={
                        <Checkbox
                          checked={weaponIds.has(w.id!)}
                          onChange={() => toggleWeapon(w.id!)}
                        />
                      }
                      label={
                        <>
                          {w.name}
                          {isPistol(w) && (
                            <Chip label="Pistol" size="small" sx={{ ml: 0.5 }} />
                          )}
                          <Typography variant="body2" color="text.secondary" component="span">
                            {" "}
                            S{w.strength} AP{w.ap === 0 ? "0" : `-${w.ap}`} D{w.damage} ·{" "}
                            {w.attacks} attacks ·{" "}
                            {w.carrier_count === 0
                              ? "all models"
                              : `${w.carrier_count} model${w.carrier_count === 1 ? "" : "s"}`}
                          </Typography>
                        </>
                      }
                    />
                  ))}
                </Stack>
                {isShooting && (
                  <Typography variant="body2" color="text.secondary">
                    {freeToMix
                      ? "Monsters and Vehicles may fire pistols alongside everything else."
                      : "A model fires either its pistols or its other weapons, never both."}
                  </Typography>
                )}
              </Paper>
            )}
            {mixesPistols && (
              <Typography color="error" sx={{ mt: 1 }}>
                Pistols cannot be fired together with other weapons.
              </Typography>
            )}
            {attackerState?.has_shot && (
              <Typography color="error" sx={{ mt: 1 }}>
                This unit has already shot this phase.
              </Typography>
            )}
          </CardContent>
        </Card>

        <Typography
          variant="h6"
          align="center"
          sx={{ alignSelf: "center", color: "primary.main", fontWeight: 800 }}
        >
          VS
        </Typography>

        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Target
            </Typography>
            <TextField
              select
              label="Enemy unit"
              value={defenderId}
              onChange={(e) => {
                setDefenderId(e.target.value === "" ? "" : Number(e.target.value));
                setPreview(null);
              }}
              fullWidth
            >
              <MenuItem value="">Choose a target…</MenuItem>
              {enemyUnits.map((u) => (
                <MenuItem key={u.id} value={u.id} disabled={state.get(u.id!)?.is_destroyed}>
                  {u.name} (T{u.toughness} Sv{u.save}+ W{u.wounds}x{u.model_count})
                  {condition(u.id)}
                </MenuItem>
              ))}
            </TextField>
            {enemyUnits.length === 0 && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                No opposing units have been fielded in this game.
              </Typography>
            )}
          </CardContent>
        </Card>
      </Box>

      <Stack direction="row" spacing={1.5} sx={{ my: 2 }}>
        <Button
          variant={isShooting ? "outlined" : "contained"}
          sx={{ flex: 1 }}
          disabled={busy || !ready}
          onClick={showPreview}
        >
          {isShooting ? "Preview odds" : "Work out the odds"}
        </Button>
        {isShooting && (
          <Button
            variant="contained"
            sx={{ flex: 2 }}
            disabled={busy || !ready}
            onClick={rollAttack}
          >
            {busy ? "Rolling…" : "🎲 Roll to hit"}
          </Button>
        )}
      </Stack>

      {preview?.map((result, i) => (
        <DiceMathBreakdown key={i} result={result} />
      ))}
    </>
  );
}
