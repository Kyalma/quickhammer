import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function Layout() {
  const { player, logout } = useAuth();

  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">
          QuickHammer
        </Link>
        {player && (
          <nav>
            <NavLink to="/roster">Roster</NavLink>
            <NavLink to="/lobby">Play</NavLink>
          </nav>
        )}
        {player && (
          <button onClick={logout} title={`Logged in as ${player.name}`}>
            {player.name} ⏻
          </button>
        )}
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  );
}
