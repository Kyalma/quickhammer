import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "../api/client";
import type { Player, TokenResponse } from "../api/types";

interface AuthState {
  player: Player | null;
  loading: boolean;
  login: (name: string, password: string) => Promise<void>;
  register: (name: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [player, setPlayer] = useState<Player | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore the session from a stored token on first load.
  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api
      .get<Player>("/api/players/me")
      .then(setPlayer)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  async function handleAuth(path: string, name: string, password: string) {
    const result = await api.post<TokenResponse>(path, { name, password });
    setToken(result.token);
    setPlayer(result.player);
  }

  const value: AuthState = {
    player,
    loading,
    login: (name, password) => handleAuth("/api/players/login", name, password),
    register: (name, password) => handleAuth("/api/players/register", name, password),
    logout: () => {
      setToken(null);
      setPlayer(null);
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
