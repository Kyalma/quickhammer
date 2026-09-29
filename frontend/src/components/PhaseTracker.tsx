import Box from "@mui/material/Box";
import { PHASES } from "../api/types";

/**
 * Five equal segments, current one filled. Deliberately not a MUI `Stepper`:
 * that adds connectors and numbered icons, and has no notion of "done" reading
 * as a colour rather than a checkmark.
 */
export function PhaseTracker({ current }: { current: number }) {
  return (
    <Box sx={{ display: "flex", gap: 0.5, my: 2 }}>
      {PHASES.map((phase, index) => {
        const isCurrent = index === current;
        const isDone = index < current;
        return (
          <Box
            key={phase}
            sx={{
              flex: 1,
              textAlign: "center",
              py: 0.75,
              px: 0.25,
              borderRadius: 1,
              border: 1,
              fontSize: { xs: "0.78rem", sm: "0.9rem" },
              fontWeight: isCurrent ? 700 : 400,
              borderColor: isCurrent ? "primary.main" : "divider",
              bgcolor: isCurrent ? "primary.main" : "action.hover",
              color: isCurrent
                ? "primary.contrastText"
                : isDone
                  ? "success.main"
                  : "text.secondary",
            }}
          >
            {phase}
          </Box>
        );
      })}
    </Box>
  );
}
