import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { api } from "../api/client";
import type { ArmyUnitSummary, BattleShockResult, Game, GamePlayer } from "../api/types";

/**
 * The 10th-edition Command phase: gain a Command Point, then take a
 * Battle-shock test for every unit below half strength. The app never rolls;
 * the player enters the 2D6 total they rolled on the table.
 */
export function CommandPhasePanel({
  code,
  me,
  onChange,
}: {
  code: string;
  me: GamePlayer;
  onChange: (game: Game) => void;
}) {
  const [rolls, setRolls] = useState<Record<number, string>>({});
  const [outcomes, setOutcomes] = useState<Record<number, BattleShockResult>>({});
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pending = me.army.filter((u) => u.needs_shock_test);
  const shocked = me.army.filter((u) => u.is_battle_shocked && !u.is_destroyed);

  async function test(unit: ArmyUnitSummary) {
    const roll = Number(rolls[unit.id]);
    if (!Number.isInteger(roll) || roll < 2 || roll > 12) {
      setError("Enter the 2D6 total you rolled, from 2 to 12.");
      return;
    }
    setBusyId(unit.id);
    setError(null);
    try {
      const result = await api.post<BattleShockResult>(
        `/api/games/${code}/units/${unit.id}/battle-shock`,
        { roll },
      );
      setOutcomes((prev) => ({ ...prev, [unit.id]: result }));
      onChange(result.game);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not resolve the test");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Command phase
        </Typography>
        <Typography sx={{ fontSize: "1.1rem" }}>
          Command points:{" "}
          <Box component="span" sx={{ color: "primary.main", fontWeight: 700 }}>
            {me.command_points}
          </Box>
        </Typography>

        <Typography variant="subtitle1" sx={{ mt: 1.5, fontWeight: 600 }}>
          Battle-shock
        </Typography>
        {pending.length === 0 && shocked.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            No unit is below half strength, so no Battle-shock tests are needed.
          </Typography>
        )}

        <Stack divider={<Divider />} spacing={1}>
          {pending.map((unit) => {
            const outcome = outcomes[unit.id];
            return (
              <Stack key={unit.id} spacing={1} sx={{ pt: 0.5 }}>
                <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
                  <Typography sx={{ fontWeight: 700 }}>{unit.name}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {unit.models_remaining} / {unit.model_count} models · Ld {unit.leadership}+
                  </Typography>
                </Stack>
                {outcome ? (
                  <Typography
                    variant="body2"
                    color={outcome.passed ? "text.secondary" : "error"}
                  >
                    Rolled {outcome.roll} against Ld {outcome.leadership}+:{" "}
                    {outcome.passed ? "passed" : "failed, unit is Battle-shocked"}
                  </Typography>
                ) : (
                  <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                    <TextField
                      label="Your 2D6 roll"
                      type="number"
                      value={rolls[unit.id] ?? ""}
                      onChange={(e) =>
                        setRolls((prev) => ({ ...prev, [unit.id]: e.target.value }))
                      }
                      slotProps={{ htmlInput: { min: 2, max: 12, inputMode: "numeric" } }}
                      sx={{ flexGrow: 1 }}
                    />
                    <Button
                      variant="contained"
                      disabled={busyId === unit.id}
                      onClick={() => test(unit)}
                      sx={{ flexShrink: 0 }}
                    >
                      Test
                    </Button>
                  </Stack>
                )}
              </Stack>
            );
          })}
        </Stack>

        {error && <Typography color="error">{error}</Typography>}

        {shocked.length > 0 && (
          <>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
              Battle-shocked until the start of your next Command phase. Objective Control counts
              as 0, no Stratagems, and Desperate Escape tests when Falling Back.
            </Typography>
            <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", rowGap: 1, mt: 1 }}>
              {shocked.map((unit) => (
                <Chip key={unit.id} label={unit.name} size="small" color="error" />
              ))}
            </Stack>
          </>
        )}
      </CardContent>
    </Card>
  );
}
