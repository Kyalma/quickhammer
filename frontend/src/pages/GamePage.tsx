import CasinoIcon from "@mui/icons-material/Casino";
import GpsFixedIcon from "@mui/icons-material/GpsFixed";
import SportsMmaIcon from "@mui/icons-material/SportsMma";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Link from "@mui/material/Link";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { api } from "../api/client";
import { factionLabel, PHASES, type Game } from "../api/types";
import { ArmySelector } from "../components/ArmySelector";
import { ArmyStatusPanel } from "../components/ArmyStatusPanel";
import { CommandPhasePanel } from "../components/CommandPhasePanel";
import { PhaseTracker } from "../components/PhaseTracker";
import { useAuth } from "../context/AuthContext";
import { usePolling } from "../hooks/usePolling";

const POLL_MS = 2500;

export function GamePage() {
  const { code } = useParams();
  const { player } = useAuth();
  const [game, setGame] = useState<Game | null>(null);
  const [error, setError] = useState<string | null>(null);

  usePolling(
    () => {
      api.get<Game>(`/api/games/${code}`).then(setGame).catch((e) => setError(e.message));
    },
    POLL_MS,
    game?.status !== "finished",
  );

  if (error) return <Typography color="error">{error}</Typography>;
  if (!game || !player) {
    return (
      <Typography variant="body2" color="text.secondary">
        Loading game…
      </Typography>
    );
  }

  const me = game.players.find((gp) => gp.player.id === player.id);
  const isMyTurn = game.active_player_id === player.id;
  const activePlayer = game.players.find((gp) => gp.player.id === game.active_player_id);
  const phaseName = PHASES[game.current_phase];
  const combatPhase = phaseName === "Shooting" || phaseName === "Fight";

  async function act(path: string) {
    setError(null);
    try {
      const updated = await api.post<Game>(`/api/games/${code}/${path}`);
      setGame(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    }
  }

  // --- Lobby view ---------------------------------------------------------
  if (game.status === "lobby") {
    return (
      <>
        <Typography variant="h5" gutterBottom>
          Waiting for players
        </Typography>
        <Card sx={{ mb: 2 }}>
          <CardContent sx={{ textAlign: "center" }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Share this code with your opponents:
            </Typography>
            <Box
              sx={{
                display: "inline-block",
                fontFamily: "ui-monospace, Consolas, monospace",
                fontSize: "1.6rem",
                letterSpacing: "0.3em",
                bgcolor: "action.hover",
                px: 1.5,
                py: 0.75,
                borderRadius: 1,
              }}
            >
              {game.code}
            </Box>
          </CardContent>
        </Card>
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Stack spacing={1}>
              {game.players.map((gp) => (
                <Stack
                  key={gp.player.id}
                  direction="row"
                  spacing={1}
                  sx={{ alignItems: "center", flexWrap: "wrap" }}
                >
                  <Typography>{gp.player.name}</Typography>
                  <Chip
                    label={gp.is_ready ? "Ready" : "Not ready"}
                    size="small"
                    color={gp.is_ready ? "success" : "default"}
                  />
                  {gp.army.length > 0 && (
                    <Typography variant="body2" color="text.secondary">
                      {factionLabel(gp.faction)}, {gp.army.length} unit
                      {gp.army.length === 1 ? "" : "s"}
                      {gp.army_points > 0 && <> · {gp.army_points} pts</>}
                    </Typography>
                  )}
                </Stack>
              ))}
              {game.players.length < 2 && (
                <Typography variant="body2" color="text.secondary">
                  At least two players are needed to start.
                </Typography>
              )}
            </Stack>
          </CardContent>
        </Card>

        {me && <ArmySelector code={game.code} me={me} onSaved={setGame} />}

        <Button
          variant="contained"
          fullWidth
          onClick={() => act("ready")}
          disabled={!me?.is_ready && (me?.army.length ?? 0) === 0}
        >
          {me?.is_ready ? "Cancel ready" : "I am ready"}
        </Button>
        {!me?.is_ready && (me?.army.length ?? 0) === 0 && (
          <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 1 }}>
            Confirm your army before readying up.
          </Typography>
        )}
      </>
    );
  }

  // --- Finished view --------------------------------------------------------
  if (game.status === "finished") {
    return (
      <>
        <Typography variant="h5" gutterBottom>
          Game over
        </Typography>
        <Typography>
          This match has ended.{" "}
          <Link component={RouterLink} to="/lobby">
            Back to the lobby
          </Link>
        </Typography>
      </>
    );
  }

  // --- Active game ----------------------------------------------------------
  return (
    <>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Typography variant="h5" sx={{ flexGrow: 1 }}>
          Round {game.current_round}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Game {game.code}
        </Typography>
      </Stack>
      <Typography>
        {isMyTurn ? (
          <Box component="span" sx={{ fontWeight: 700 }}>
            Your turn
          </Box>
        ) : (
          <>
            Waiting for{" "}
            <Box component="span" sx={{ fontWeight: 700 }}>
              {activePlayer?.player.name ?? "…"}
            </Box>
          </>
        )}{" "}
        — {phaseName} Phase
      </Typography>
      <PhaseTracker current={game.current_phase} />

      {me && isMyTurn && phaseName === "Command" && (
        <CommandPhasePanel code={game.code} me={me} onChange={setGame} />
      )}

      {combatPhase && isMyTurn && (
        <Button
          variant="contained"
          fullWidth
          component={RouterLink}
          to={`/games/${game.code}/combat`}
          startIcon={phaseName === "Shooting" ? <GpsFixedIcon /> : <SportsMmaIcon />}
          sx={{ mb: 2 }}
        >
          {phaseName === "Shooting" ? "Shoot" : "Resolve an attack"}
        </Button>
      )}

      {game.pending_attack_id !== null && !isMyTurn && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography gutterBottom>
              <Box component="span" sx={{ fontWeight: 700 }}>
                {activePlayer?.player.name ?? "Your opponent"}
              </Box>{" "}
              is resolving an attack.
            </Typography>
            <Button
              fullWidth
              component={RouterLink}
              to={`/games/${game.code}/attacks/${game.pending_attack_id}`}
              startIcon={<CasinoIcon />}
            >
              Watch the dice
            </Button>
          </CardContent>
        </Card>
      )}

      {isMyTurn && (
        <Button fullWidth onClick={() => act("advance")} sx={{ mb: 2 }}>
          {game.current_phase === PHASES.length - 1 ? "End my turn" : "Next phase →"}
        </Button>
      )}

      {me && <ArmyStatusPanel code={game.code} me={me} onChange={setGame} />}

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Players
          </Typography>
          <Stack spacing={0.5}>
            {game.players.map((gp) => (
              <Typography key={gp.player.id}>
                {gp.player.name}
                {gp.player.id === game.active_player_id && " ← active"}
                <Typography variant="body2" color="text.secondary" component="span">
                  {" — "}
                  {factionLabel(gp.faction)},{" "}
                  {gp.army.filter((u) => !u.is_destroyed).length}/{gp.army.length} unit
                  {gp.army.length === 1 ? "" : "s"} left
                  {gp.army_points > 0 && <> · {gp.army_points} pts</>} · {gp.command_points} CP
                </Typography>
              </Typography>
            ))}
          </Stack>
          <Button color="error" onClick={() => act("finish")} sx={{ mt: 1.5 }}>
            End game
          </Button>
        </CardContent>
      </Card>
    </>
  );
}
