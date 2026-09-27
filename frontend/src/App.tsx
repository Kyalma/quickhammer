import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { useAuth } from "./context/AuthContext";
import { CombatPage } from "./pages/CombatPage";
import { GamePage } from "./pages/GamePage";
import { LibraryPage } from "./pages/LibraryPage";
import { LobbyPage } from "./pages/LobbyPage";
import { LoginPage } from "./pages/LoginPage";
import { RosterPage } from "./pages/RosterPage";
import { UnitEditorPage } from "./pages/UnitEditorPage";

function RequireAuth({ children }: { children: JSX.Element }) {
  const { player, loading } = useAuth();
  if (loading) return <p className="note">Loading…</p>;
  if (!player) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Navigate to="/roster" replace />} />
        <Route path="/roster" element={<RequireAuth><RosterPage /></RequireAuth>} />
        <Route path="/units/:unitId" element={<RequireAuth><UnitEditorPage /></RequireAuth>} />
        <Route path="/library" element={<RequireAuth><LibraryPage /></RequireAuth>} />
        <Route path="/lobby" element={<RequireAuth><LobbyPage /></RequireAuth>} />
        <Route path="/games/:code" element={<RequireAuth><GamePage /></RequireAuth>} />
        <Route path="/games/:code/combat" element={<RequireAuth><CombatPage /></RequireAuth>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
