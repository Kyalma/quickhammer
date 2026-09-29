import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Link from "@mui/material/Link";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { LibraryFaction, LibraryUnitSummary, Unit } from "../api/types";

const SEARCH_DEBOUNCE_MS = 350;

export function LibraryPage() {
  const navigate = useNavigate();
  const [factions, setFactions] = useState<LibraryFaction[]>([]);
  const [faction, setFaction] = useState("");
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<LibraryUnitSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [importingId, setImportingId] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<LibraryFaction[]>("/api/library/factions")
      .then(setFactions)
      .catch((e) => setError(e.message));
  }, []);

  // Debounced search whenever the query or faction changes.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (faction) params.set("faction", faction);
      api
        .get<LibraryUnitSummary[]>(`/api/library/units?${params}`)
        .then(setResults)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [search, faction]);

  async function importUnit(entry: LibraryUnitSummary) {
    setImportingId(entry.id);
    setError(null);
    try {
      const unit = await api.post<Unit>(`/api/library/units/${entry.id}/import`);
      // Land in the editor so stats, model count, and picture can be adjusted.
      navigate(`/units/${unit.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
      setImportingId(null);
    }
  }

  return (
    <>
      <Typography variant="h5" gutterBottom>
        Unit library
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Search official 40k datasheets and add them to your roster. Imported units open in the
        editor, so you can tweak stats or{" "}
        <Link component={RouterLink} to="/units/new">
          build one from scratch
        </Link>
        .
      </Typography>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
            <TextField
              label="Search units"
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="e.g. intercessor, boyz, wraith…"
              sx={{ flex: 2 }}
              fullWidth
            />
            <TextField
              select
              label="Faction"
              value={faction}
              onChange={(e) => setFaction(e.target.value)}
              sx={{ flex: 1 }}
              fullWidth
            >
              <MenuItem value="">All factions</MenuItem>
              {factions.map((f) => (
                <MenuItem key={f.name} value={f.name}>
                  {f.name} ({f.unit_count})
                </MenuItem>
              ))}
            </TextField>
          </Stack>
        </CardContent>
      </Card>

      {error && <Typography color="error">{error}</Typography>}
      {loading && (
        <Typography variant="body2" color="text.secondary">
          Searching…
        </Typography>
      )}
      {results && results.length === 0 && !loading && (
        <Typography variant="body2" color="text.secondary">
          No units match. Try a shorter search or another faction.
        </Typography>
      )}

      <Stack spacing={2}>
        {results?.map((entry) => (
          <Card key={entry.id}>
            <CardContent>
              <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
                <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                  <Typography sx={{ fontWeight: 700 }}>
                    {entry.name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {entry.faction}
                    {entry.points != null && <> · {entry.points} pts</>}
                    {entry.min_models != null && entry.max_models != null && (
                      <>
                        {" · "}
                        {entry.min_models === entry.max_models
                          ? `${entry.min_models} model${entry.min_models > 1 ? "s" : ""}`
                          : `${entry.min_models}–${entry.max_models} models`}
                      </>
                    )}
                  </Typography>
                </Box>
                <Button
                  variant="contained"
                  disabled={importingId !== null}
                  onClick={() => importUnit(entry)}
                  sx={{ flexShrink: 0 }}
                >
                  {importingId === entry.id ? "Importing…" : "Import"}
                </Button>
              </Stack>
            </CardContent>
          </Card>
        ))}
      </Stack>
    </>
  );
}
