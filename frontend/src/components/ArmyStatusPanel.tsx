import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { api } from "../api/client";
import type { ArmyUnitSummary, Game, GamePlayer } from "../api/types";

/**
 * Your army's live condition during a game, with controls to record casualties.
 * Players update their own units, the same way you remove your own models at
 * the table.
 */
export function ArmyStatusPanel({
  code,
  me,
  onChange,
}: {
  code: string;
  me: GamePlayer;
  onChange: (game: Game) => void;
}) {
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function applyWounds(unit: ArmyUnitSummary, wounds: number) {
    setBusyId(unit.id);
    setError(null);
    try {
      onChange(
        await api.post<Game>(`/api/games/${code}/units/${unit.id}/damage`, { wounds }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update that unit");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Your army
        </Typography>
        {error && <Typography color="error">{error}</Typography>}
        <Stack divider={<Divider />} spacing={1}>
          {me.army.map((unit) => (
            <Stack key={unit.id} spacing={0.5} sx={{ pt: 0.5 }}>
              <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
                <Typography
                  sx={{
                    fontWeight: 700,
                    ...(unit.is_destroyed
                      ? { textDecoration: "line-through", color: "text.secondary" }
                      : {}),
                  }}
                >
                  {unit.name}
                </Typography>
                {unit.is_destroyed && <Chip label="Destroyed" size="small" color="error" />}
                {unit.is_battle_shocked && !unit.is_destroyed && (
                  <Chip label="Battle-shocked" size="small" color="error" />
                )}
                {unit.below_half_strength && !unit.is_destroyed && !unit.is_battle_shocked && (
                  <Chip label="Below half" size="small" />
                )}
              </Stack>
              <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
                <Typography variant="body2" color="text.secondary" sx={{ flexGrow: 1 }}>
                  {unit.models_remaining} / {unit.model_count} model
                  {unit.model_count === 1 ? "" : "s"}
                  {unit.wounds > 1 && unit.wounds_lost > 0 && (
                    <>
                      {" "}
                      · lead model on {unit.wounds - unit.wounds_lost} / {unit.wounds} wounds
                    </>
                  )}
                </Typography>
                <Tooltip title="Undo one wound">
                  <span>
                    <Button
                      size="small"
                      disabled={busyId === unit.id}
                      onClick={() => applyWounds(unit, -1)}
                    >
                      + 1 W
                    </Button>
                  </span>
                </Tooltip>
                <Tooltip title="Record one wound">
                  <span>
                    <Button
                      size="small"
                      disabled={busyId === unit.id || unit.is_destroyed}
                      onClick={() => applyWounds(unit, 1)}
                    >
                      − 1 W
                    </Button>
                  </span>
                </Tooltip>
              </Stack>
            </Stack>
          ))}
        </Stack>
      </CardContent>
    </Card>
  );
}
