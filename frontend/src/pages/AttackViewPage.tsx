import Link from "@mui/material/Link";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useEffect, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { AttackRoll } from "../api/types";
import { DiceRollTrack } from "../components/DiceRollTrack";

/** Read-only view of an attack, so the defending player sees the same dice. */
export function AttackViewPage() {
  const { code, rollId } = useParams();
  const [roll, setRoll] = useState<AttackRoll | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<AttackRoll>(`/api/games/${code}/shooting/${rollId}`)
      .then(setRoll)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load that attack"),
      );
  }, [code, rollId]);

  return (
    <>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 2 }}>
        <Typography variant="h5" sx={{ flexGrow: 1 }}>
          {roll ? `${roll.attacker_name} → ${roll.target_name}` : "Attack"}
        </Typography>
        <Link component={RouterLink} to={`/games/${code}`} sx={{ flexShrink: 0 }}>
          ← Back to game
        </Link>
      </Stack>
      {error && <Typography color="error">{error}</Typography>}
      {!roll && !error && (
        <Typography variant="body2" color="text.secondary">
          Loading the dice…
        </Typography>
      )}
      {roll && (
        <>
          <DiceRollTrack rolls={roll.rolls} />
          <Typography variant="body2" color="text.secondary">
            {roll.resolved
              ? roll.applied
                ? "This result has been applied."
                : "This result was discarded."
              : "Waiting for your opponent to confirm."}
          </Typography>
        </>
      )}
    </>
  );
}
