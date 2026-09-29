import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { GAME_STATUS_LABELS, type Game, type GameSummary } from "../api/types";
import { usePolling } from "../hooks/usePolling";
import { useConfirm } from "../hooks/useConfirm";

const POLL_MS = 4000;

export function LobbyPage() {
  const navigate = useNavigate();
  const [games, setGames] = useState<GameSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, confirmDialog] = useConfirm();

  const refresh = useCallback(() => {
    api
      .get<GameSummary[]>("/api/games")
      .then(setGames)
      .catch((err) => setError(err.message));
  }, []);

  // Keep the list fresh so games others open appear without a reload.
  usePolling(refresh, POLL_MS);

  async function createGame() {
    setError(null);
    setBusy(true);
    try {
      const game = await api.post<Game>("/api/games");
      navigate(`/games/${game.code}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create game");
    } finally {
      setBusy(false);
    }
  }

  async function joinGame(code: string) {
    setError(null);
    setBusy(true);
    try {
      await api.post<Game>(`/api/games/${code}/join`);
      navigate(`/games/${code}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not join game");
      setBusy(false);
    }
  }

  async function deleteGame(game: GameSummary) {
    const ok = await confirm({
      title: `Delete game ${game.code}?`,
      message: "This cannot be undone. Rosters are kept.",
    });
    if (!ok) return;
    setError(null);
    setBusy(true);
    try {
      await api.delete(`/api/games/${game.code}`);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete game");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {confirmDialog}
      <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 2 }}>
        <Typography variant="h5" sx={{ flexGrow: 1 }}>
          Play
        </Typography>
        <Button variant="contained" disabled={busy} onClick={createGame}>
          New game
        </Button>
      </Stack>
      {error && <Typography color="error">{error}</Typography>}

      {games && games.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No games yet. Create one and share it with your opponents.
        </Typography>
      )}
      {!games && !error && (
        <Typography variant="body2" color="text.secondary">
          Loading games…
        </Typography>
      )}

      <Stack spacing={2}>
        {games?.map((game) => (
          <Card key={game.id}>
            <CardContent>
              <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
                <Typography sx={{ fontWeight: 700 }}>{game.code}</Typography>
                <Chip
                  label={GAME_STATUS_LABELS[game.status]}
                  size="small"
                  color={game.status === "active" ? "success" : "default"}
                />
                {game.is_member && (
                  <Typography variant="body2" color="text.secondary">
                    you are in this game
                  </Typography>
                )}
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {game.player_count} player{game.player_count === 1 ? "" : "s"}
                {game.player_names.length > 0 && <>: {game.player_names.join(", ")}</>}
                {game.creator_name && <> · opened by {game.creator_name}</>}
                {game.status === "active" && (
                  <>
                    {" "}
                    · round {game.current_round}, {game.phase_name}
                  </>
                )}
              </Typography>
              <Stack direction="row" spacing={1.5} sx={{ mt: 1.5 }}>
                {game.is_member ? (
                  <Button
                    variant="contained"
                    sx={{ flexGrow: 1 }}
                    onClick={() => navigate(`/games/${game.code}`)}
                  >
                    {game.status === "lobby" ? "Back to lobby" : "Open"}
                  </Button>
                ) : game.can_join ? (
                  <Button
                    variant="contained"
                    sx={{ flexGrow: 1 }}
                    disabled={busy}
                    onClick={() => joinGame(game.code)}
                  >
                    Join
                  </Button>
                ) : (
                  <Button sx={{ flexGrow: 1 }} disabled>
                    {game.status === "lobby" ? "Full" : "In progress"}
                  </Button>
                )}
                {game.can_delete && (
                  <Button
                    color="error"
                    disabled={busy}
                    onClick={() => deleteGame(game)}
                    sx={{ flexShrink: 0 }}
                  >
                    Delete
                  </Button>
                )}
              </Stack>
            </CardContent>
          </Card>
        ))}
      </Stack>
    </>
  );
}
