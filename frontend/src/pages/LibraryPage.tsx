import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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
    api.get<LibraryFaction[]>("/api/library/factions")
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
      api.get<LibraryUnitSummary[]>(`/api/library/units?${params}`)
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
      <h1>Unit library</h1>
      <p className="note">
        Search official 40k datasheets and add them to your roster. Imported units open
        in the editor, so you can tweak stats or <Link to="/units/new">build one from scratch</Link>.
      </p>

      <div className="card">
        <div className="row">
          <div className="field" style={{ flex: 2 }}>
            <label htmlFor="lib-search">Search units</label>
            <input
              id="lib-search"
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="e.g. intercessor, boyz, wraith…"
            />
          </div>
          <div className="field">
            <label htmlFor="lib-faction">Faction</label>
            <select id="lib-faction" value={faction} onChange={(e) => setFaction(e.target.value)}>
              <option value="">All factions</option>
              {factions.map((f) => (
                <option key={f.name} value={f.name}>
                  {f.name} ({f.unit_count})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p className="note">Searching…</p>}
      {results && results.length === 0 && !loading && (
        <p className="note">No units match. Try a shorter search or another faction.</p>
      )}

      {results?.map((entry) => (
        <div className="card row" key={entry.id} style={{ alignItems: "center" }}>
          <div style={{ flex: 3 }}>
            <b>{entry.name}</b>
            <p className="note">
              {entry.faction}
              {entry.points != null && <> · {entry.points} pts</>}
              {entry.min_models != null && entry.max_models != null && (
                <> · {entry.min_models === entry.max_models
                  ? `${entry.min_models} model${entry.min_models > 1 ? "s" : ""}`
                  : `${entry.min_models}–${entry.max_models} models`}</>
              )}
            </p>
          </div>
          <button
            className="primary"
            style={{ flex: "0 0 auto" }}
            disabled={importingId !== null}
            onClick={() => importUnit(entry)}
          >
            {importingId === entry.id ? "Importing…" : "Import"}
          </button>
        </div>
      ))}
    </>
  );
}
