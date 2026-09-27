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
    <div className="card" style={{ maxWidth: 420, margin: "2rem auto" }}>
      <h1>{mode === "login" ? "Log in" : "Create your profile"}</h1>
      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="name">Player name</label>
          <input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="username"
            required
            minLength={2}
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            minLength={4}
          />
        </div>
        {error && <p className="error">{error}</p>}
        <button className="primary" type="submit" disabled={busy} style={{ width: "100%" }}>
          {mode === "login" ? "Log in" : "Register"}
        </button>
      </form>
      <p style={{ marginTop: "1rem" }}>
        {mode === "login" ? (
          <>
            New here?{" "}
            <a href="#" onClick={(e) => { e.preventDefault(); setMode("register"); }}>
              Create a profile
            </a>
          </>
        ) : (
          <>
            Already have a profile?{" "}
            <a href="#" onClick={(e) => { e.preventDefault(); setMode("login"); }}>
              Log in
            </a>
          </>
        )}
      </p>
    </div>
  );
}
