import { keyframes } from "@emotion/react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useEffect, useState } from "react";
import type { RolledDie, ShootingRolls } from "../api/types";

const STAGE_REVEAL_MS = 550;

/** Each stage slides in as it is revealed; this is what sells the roll. */
const stageIn = keyframes`
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: none; }
`;

type DieTone = "neutral" | "good" | "fail" | "crit" | "auto";

/** Maps an outcome label to a colour. Unknown labels stay neutral. */
function dieTone(outcome: string): DieTone {
  const text = outcome.toLowerCase();
  if (text.includes("critical")) return "crit";
  if (text.startsWith("miss") || text.startsWith("no wound")) return "fail";
  if (text.includes("save failed") || text.includes("no save")) return "good";
  if (text.startsWith("saved")) return "fail";
  if (text.startsWith("hit") || text.startsWith("wounded")) return "good";
  if (text.startsWith("auto") || text.startsWith("sustained")) return "auto";
  if (text.includes("damage")) return "good";
  return "neutral";
}

const TONES = {
  neutral: { bgcolor: "action.hover", borderColor: "divider", color: "text.secondary" },
  fail: { bgcolor: "action.hover", borderColor: "divider", color: "text.secondary" },
  good: { bgcolor: "success.main", borderColor: "success.main", color: "success.contrastText" },
  crit: { bgcolor: "primary.main", borderColor: "primary.main", color: "primary.contrastText" },
  auto: {
    bgcolor: "transparent",
    borderColor: "primary.main",
    borderStyle: "dashed",
    color: "primary.main",
  },
} as const;

/**
 * A single 30px die. Deliberately not a MUI `Chip`: a Chip is a pill with its
 * own height, padding and label contract, which fights a square die face.
 */
function Die({ die }: { die: RolledDie }) {
  return (
    <Box
      title={die.outcome}
      sx={{
        width: 30,
        height: 30,
        borderRadius: 1,
        border: 1,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontWeight: 700,
        fontSize: "0.9rem",
        fontVariantNumeric: "tabular-nums",
        ...TONES[dieTone(die.outcome)],
      }}
    >
      {/* A value of 0 means no die was physically rolled (auto-hit, auto-wound,
          sustained hit, or no save possible). */}
      {die.value > 0 ? die.value : "—"}
    </Box>
  );
}

/** Distinct outcomes in this stage with counts, e.g. "6 Hit · 4 Miss". */
function outcomeTally(dice: RolledDie[]): string {
  const counts = new Map<string, number>();
  for (const die of dice) counts.set(die.outcome, (counts.get(die.outcome) ?? 0) + 1);
  return [...counts.entries()]
    .filter(([label]) => !label.includes("damage") && !label.includes("attacks"))
    .map(([label, n]) => `${n} ${label}`)
    .join(" · ");
}

export function DiceRollTrack({ rolls }: { rolls: ShootingRolls }) {
  // Reveal stages one at a time: this is most of what makes it feel like
  // rolling rather than reading a table.
  const totalStages = rolls.weapons.reduce((n, w) => n + w.stages.length, 0);
  const [revealed, setRevealed] = useState(1);

  useEffect(() => {
    setRevealed(1);
  }, [rolls]);

  useEffect(() => {
    if (revealed >= totalStages) return;
    const timer = window.setTimeout(() => setRevealed((n) => n + 1), STAGE_REVEAL_MS);
    return () => window.clearTimeout(timer);
  }, [revealed, totalStages]);

  const done = revealed >= totalStages;
  let index = 0;

  return (
    <>
      {rolls.weapons.map((weapon) => (
        <Card key={weapon.weapon} sx={{ mb: 2 }}>
          <CardContent>
            <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
              <Typography sx={{ fontWeight: 700, flexGrow: 1 }}>{weapon.weapon}</Typography>
              <Typography variant="body2" color="text.secondary">
                {weapon.models_firing} model{weapon.models_firing === 1 ? "" : "s"} firing
              </Typography>
            </Stack>
            {weapon.stages.map((stage) => {
              const visible = index++ < revealed;
              if (!visible) return null;
              const tally = outcomeTally(stage.dice);
              return (
                <Box
                  key={stage.name}
                  sx={{
                    borderTop: 1,
                    borderColor: "divider",
                    pt: 1,
                    mt: 1,
                    animation: `${stageIn} 0.25s ease-out`,
                  }}
                >
                  <Stack
                    direction="row"
                    spacing={1}
                    sx={{ alignItems: "baseline", flexWrap: "wrap", mb: 0.5 }}
                  >
                    <Typography sx={{ fontWeight: 700, flexGrow: 1 }}>{stage.name}</Typography>
                    {tally && (
                      <Typography variant="body2" color="text.secondary">
                        {tally}
                      </Typography>
                    )}
                  </Stack>
                  {stage.dice.length > 0 ? (
                    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mb: 0.5 }}>
                      {stage.dice.map((die, i) => (
                        <Die key={i} die={die} />
                      ))}
                    </Box>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      No dice
                    </Typography>
                  )}
                  <Typography variant="body2" color="text.secondary">
                    {stage.summary}
                  </Typography>
                </Box>
              );
            })}
          </CardContent>
        </Card>
      ))}

      {done && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              {rolls.outcome}
            </Typography>
            {rolls.allocation.map((line, i) => (
              <Typography key={i} variant="body2" color="text.secondary">
                {line}
              </Typography>
            ))}
            <Typography sx={{ fontSize: "1.1rem", mt: 1.5 }}>
              <Box component="span" sx={{ color: "primary.main", fontWeight: 700 }}>
                {rolls.total_damage}
              </Box>{" "}
              damage ·{" "}
              <Box component="span" sx={{ color: "primary.main", fontWeight: 700 }}>
                {rolls.models_slain}
              </Box>{" "}
              model{rolls.models_slain === 1 ? "" : "s"} slain
            </Typography>
            {rolls.notes.map((note) => (
              <Typography key={note} variant="body2" color="text.secondary">
                ℹ {note}
              </Typography>
            ))}
          </CardContent>
        </Card>
      )}
    </>
  );
}
