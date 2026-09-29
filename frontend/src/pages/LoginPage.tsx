import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Link from "@mui/material/Link";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") await login(name, password);
      else await register(name, password);
      navigate("/roster");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card sx={{ maxWidth: 420, mx: "auto", mt: 4 }}>
      <CardContent>
        <Typography variant="h5" gutterBottom>
          {mode === "login" ? "Log in" : "Create your profile"}
        </Typography>
        <form onSubmit={submit}>
          <Stack spacing={2}>
            <TextField
              label="Player name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoComplete="username"
              required
              slotProps={{ htmlInput: { minLength: 2 } }}
              fullWidth
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              slotProps={{ htmlInput: { minLength: 4 } }}
              fullWidth
            />
            {error && <Typography color="error">{error}</Typography>}
            <Button variant="contained" type="submit" disabled={busy} fullWidth>
              {mode === "login" ? "Log in" : "Register"}
            </Button>
          </Stack>
        </form>
        <Typography sx={{ mt: 2 }}>
          {mode === "login" ? (
            <>
              New here?{" "}
              <Link component="button" type="button" onClick={() => setMode("register")}>
                Create a profile
              </Link>
            </>
          ) : (
            <>
              Already have a profile?{" "}
              <Link component="button" type="button" onClick={() => setMode("login")}>
                Log in
              </Link>
            </>
          )}
        </Typography>
      </CardContent>
    </Card>
  );
}
