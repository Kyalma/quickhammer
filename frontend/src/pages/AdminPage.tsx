import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { GAME_STATUS_LABELS, type AdminGame, type AdminPlayer } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { useConfirm } from "../hooks/useConfirm";

export function AdminPage() {
  const { player } = useAuth();
  const [players, setPlayers] = useState<AdminPlayer[] | null>(null);
  const [games, setGames] = useState<AdminGame[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, confirmDialog] = useConfirm();

  const refresh = useCallback(() => {
    Promise.all([
      api.get<AdminPlayer[]>("/api/admin/players"),
      api.get<AdminGame[]>("/api/admin/games"),
    ])
      .then(([p, g]) => {
        setPlayers(p);
        setGames(g);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(refresh, [refresh]);

  async function remove(path: string, title: string, message: string) {
    if (!(await confirm({ title, message }))) return;
    setError(null);
    setBusy(true);
    try {
      await api.delete(path);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete that");
    } finally {
      setBusy(false);
    }
  }

  if (error && !players) return <Typography color="error">{error}</Typography>;
  if (!players || !games) {
    return (
      <Typography variant="body2" color="text.secondary">
        Loading…
      </Typography>
    );
  }

  return (
    <>
      {confirmDialog}
      <Typography variant="h5" gutterBottom>
        Admin
      </Typography>
      {error && <Typography color="error">{error}</Typography>}

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Users ({players.length})
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell align="right">Units</TableCell>
                  <TableCell>Role</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {players.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell>{p.name}</TableCell>
                    <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums" }}>
                      {p.unit_count}
                    </TableCell>
                    <TableCell sx={{ color: "text.secondary" }}>
                      {p.is_admin ? "Admin" : "Player"}
                    </TableCell>
                    <TableCell align="right">
                      {p.id === player?.id ? (
                        <Typography variant="body2" color="text.secondary">
                          you
                        </Typography>
                      ) : (
                        <Button
                          size="small"
                          color="error"
                          disabled={busy}
                          onClick={() =>
                            remove(
                              `/api/admin/players/${p.id}`,
                              `Delete ${p.name}?`,
                              "Their units and their place in every game go too. " +
                                "This cannot be undone.",
                            )
                          }
                        >
                          Delete
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Games ({games.length})
          </Typography>
          {games.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No games yet.
            </Typography>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Code</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Players</TableCell>
                    <TableCell>Progress</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {games.map((g) => (
                    <TableRow key={g.id}>
                      <TableCell>{g.code}</TableCell>
                      <TableCell>
                        <Chip
                          label={GAME_STATUS_LABELS[g.status]}
                          size="small"
                          color={g.status === "active" ? "success" : "default"}
                        />
                      </TableCell>
                      <TableCell sx={{ color: "text.secondary" }}>
                        {g.player_names.join(", ") || "—"}
                      </TableCell>
                      <TableCell sx={{ color: "text.secondary" }}>
                        {g.status === "active"
                          ? `Round ${g.current_round}, ${g.phase_name} (${g.active_player ?? "?"})`
                          : "—"}
                      </TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          color="error"
                          disabled={busy}
                          onClick={() =>
                            remove(
                              `/api/admin/games/${g.id}`,
                              `Delete game ${g.code}?`,
                              "Rosters are kept. This cannot be undone.",
                            )
                          }
                        >
                          Delete
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      <Typography variant="body2" color="text.secondary">
        Admin rights are granted from the server console:{" "}
        <Box component="code" sx={{ fontFamily: "monospace" }}>
          docker exec -it QuickHammer python scripts/make_admin.py &lt;name&gt;
        </Box>
      </Typography>
    </>
  );
}
