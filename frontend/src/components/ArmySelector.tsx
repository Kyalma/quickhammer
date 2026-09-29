import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Checkbox from "@mui/material/Checkbox";
import FormControl from "@mui/material/FormControl";
import FormControlLabel from "@mui/material/FormControlLabel";
import FormLabel from "@mui/material/FormLabel";
import Paper from "@mui/material/Paper";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
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
  // ArmyUnitSummary carries two ids: `id` is the game_units row, `unit_id` is
  // the roster Unit. This set holds roster Unit ids, because that is what the
  // checkboxes match on and what POST /army resolves.
  const [selected, setSelected] = useState<Set<number>>(
    () => new Set(me.army.map((u) => u.unit_id)),
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
        // Send exactly what is ticked on screen, rather than the raw set, so a
        // selection can never drift from what the player can see.
        unit_ids: selectedUnits.map((u) => u.id!),
      });
      onSaved(game);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your army");
    } finally {
      setSaving(false);
    }
  }

  if (error && !units) return <Typography color="error">{error}</Typography>;
  if (!units) {
    return (
      <Typography variant="body2" color="text.secondary">
        Loading your roster…
      </Typography>
    );
  }

  if (units.length === 0) {
    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Your army
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Your roster is empty. Add units in Roster before joining a game.
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Your army
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Pick one faction, then the units you are fielding.
        </Typography>

        <Paper variant="outlined" sx={{ p: 1.5, mb: 1.5 }}>
          <FormControl>
            <FormLabel id="faction-label">Faction</FormLabel>
            <RadioGroup
              aria-labelledby="faction-label"
              value={faction ?? ""}
              onChange={(e) => chooseFaction(e.target.value)}
            >
              {byFaction.map(([value, factionsUnits]) => (
                <FormControlLabel
                  key={value}
                  value={value}
                  control={<Radio />}
                  label={
                    <>
                      {factionLabel(value)}{" "}
                      <Typography variant="body2" color="text.secondary" component="span">
                        ({factionsUnits.length} unit{factionsUnits.length > 1 ? "s" : ""})
                      </Typography>
                    </>
                  }
                />
              ))}
            </RadioGroup>
          </FormControl>
        </Paper>

        {faction !== null && (
          <Paper variant="outlined" sx={{ p: 1.5, mb: 1.5 }}>
            <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 0.5 }}>
              <FormLabel sx={{ flexGrow: 1 }}>Units</FormLabel>
              <Button
                size="small"
                variant="text"
                onClick={() =>
                  setSelected(
                    allSelected ? new Set() : new Set(factionUnits.map((u) => u.id!)),
                  )
                }
              >
                {allSelected ? "Clear all" : "Select all"}
              </Button>
            </Stack>
            <Stack>
              {factionUnits.map((unit) => (
                <FormControlLabel
                  key={unit.id}
                  control={
                    <Checkbox
                      checked={selected.has(unit.id!)}
                      onChange={() => toggleUnit(unit.id!)}
                    />
                  }
                  label={
                    <>
                      {unit.name}
                      {unit.points > 0 && (
                        <Typography variant="body2" color="text.secondary" component="span">
                          {" "}
                          · {unit.points} pts
                        </Typography>
                      )}
                    </>
                  }
                />
              ))}
            </Stack>
          </Paper>
        )}

        {error && <Typography color="error">{error}</Typography>}

        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Typography sx={{ flexGrow: 1 }}>
            {selectedUnits.length} unit{selectedUnits.length === 1 ? "" : "s"}
            {totalPoints > 0 && (
              <>
                {" · "}
                <Box component="span" sx={{ color: "primary.main", fontWeight: 700 }}>
                  {totalPoints} pts
                </Box>
              </>
            )}
          </Typography>
          <Button
            variant="contained"
            disabled={saving || selectedUnits.length === 0}
            onClick={save}
            sx={{ flexShrink: 0 }}
          >
            {saving ? "Saving…" : "Confirm army"}
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}
