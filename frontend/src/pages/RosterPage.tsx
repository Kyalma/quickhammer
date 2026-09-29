import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Unit } from "../api/types";
import { UnitCard } from "../components/UnitCard";

const NO_FACTION = "Unaligned";

function groupByFaction(units: Unit[]): [string, Unit[]][] {
  const groups = new Map<string, Unit[]>();
  for (const unit of units) {
    const key = unit.faction.trim() || NO_FACTION;
    const list = groups.get(key) ?? [];
    list.push(unit);
    groups.set(key, list);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

export function RosterPage() {
  const navigate = useNavigate();
  const [units, setUnits] = useState<Unit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Unit[]>("/api/units")
      .then(setUnits)
      .catch((err) => setError(err.message));
  }, []);

  const factions = useMemo(() => groupByFaction(units ?? []), [units]);
  const grandTotal = useMemo(
    () => (units ?? []).reduce((sum, u) => sum + u.points, 0),
    [units],
  );

  return (
    <>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap", mb: 2 }}>
        <Typography variant="h5" sx={{ flexGrow: 1 }}>
          My roster
        </Typography>
        <Button variant="contained" onClick={() => navigate("/library")}>
          From library
        </Button>
        <Button onClick={() => navigate("/units/new")}>New unit</Button>
      </Stack>
      {error && <Typography color="error">{error}</Typography>}
      {units && units.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No units yet. Create your first unit to get started.
        </Typography>
      )}

      {factions.map(([faction, factionUnits]) => {
        const total = factionUnits.reduce((sum, u) => sum + u.points, 0);
        return (
          <Box key={faction} component="section" sx={{ mb: 3 }}>
            <Stack
              direction="row"
              spacing={1}
              sx={{
                alignItems: "baseline",
                justifyContent: "space-between",
                borderBottom: 1,
                borderColor: "divider",
                pb: 0.5,
                mb: 1.5,
              }}
            >
              <Typography variant="h6" color="primary">
                {faction}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {factionUnits.length} unit{factionUnits.length > 1 ? "s" : ""}
                {total > 0 && (
                  <>
                    {" · "}
                    <Box component="span" sx={{ color: "text.primary", fontWeight: 600 }}>
                      {total} pts
                    </Box>
                  </>
                )}
              </Typography>
            </Stack>
            <Box
              sx={{
                display: "grid",
                gap: 2,
                gridTemplateColumns: {
                  xs: "1fr",
                  sm: "repeat(2, 1fr)",
                  md: "repeat(3, 1fr)",
                },
              }}
            >
              {factionUnits.map((unit) => (
                <UnitCard
                  key={unit.id}
                  unit={unit}
                  onClick={() => navigate(`/units/${unit.id}`)}
                />
              ))}
            </Box>
          </Box>
        );
      })}

      {factions.length > 1 && grandTotal > 0 && (
        <Typography variant="body2" color="text.secondary" align="right">
          Roster total:{" "}
          <Box component="span" sx={{ color: "text.primary", fontWeight: 600 }}>
            {grandTotal} pts
          </Box>
        </Typography>
      )}
    </>
  );
}
