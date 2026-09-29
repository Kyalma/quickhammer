import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import type { Unit } from "../api/types";

/** One statline entry: dim label, bright value. */
function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Typography variant="body2" color="text.secondary" component="span">
      {label}{" "}
      <Box component="span" sx={{ color: "text.primary", fontWeight: 600 }}>
        {value}
      </Box>
    </Typography>
  );
}

export function UnitCard({ unit, onClick }: { unit: Unit; onClick?: () => void }) {
  const body = (
    <CardContent>
      <Stack direction="row" spacing={1.5}>
        <Box
          component={unit.image_path ? "img" : "div"}
          src={unit.image_path ?? undefined}
          alt={unit.image_path ? unit.name : undefined}
          sx={{
            width: 72,
            height: 72,
            flexShrink: 0,
            borderRadius: 1,
            objectFit: "cover",
            bgcolor: "action.hover",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "text.secondary",
            fontSize: "1.5rem",
          }}
        >
          {unit.image_path ? undefined : "⚔"}
        </Box>
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Stack direction="row" spacing={1} sx={{ justifyContent: "space-between" }}>
            <Typography variant="h6">{unit.name}</Typography>
            {unit.points > 0 && (
              <Chip label={`${unit.points} pts`} size="small" color="primary" variant="outlined" />
            )}
          </Stack>
          <Stack direction="row" sx={{ flexWrap: "wrap", columnGap: 1, rowGap: 0.25, mt: 0.5 }}>
            <Stat label="M" value={`${unit.movement}"`} />
            <Stat label="T" value={String(unit.toughness)} />
            <Stat label="Sv" value={`${unit.save}+`} />
            {unit.invuln_save != null && <Stat label="Inv" value={`${unit.invuln_save}++`} />}
            <Stat label="W" value={String(unit.wounds)} />
            <Stat label="OC" value={String(unit.oc)} />
            <Stat label="Models" value={String(unit.model_count)} />
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {unit.weapons.length > 0
              ? unit.weapons.map((w) => w.name).join(", ")
              : "No weapons yet"}
          </Typography>
        </Box>
      </Stack>
    </CardContent>
  );

  return (
    <Card>{onClick ? <CardActionArea onClick={onClick}>{body}</CardActionArea> : body}</Card>
  );
}
