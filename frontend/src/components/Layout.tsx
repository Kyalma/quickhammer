import LogoutIcon from "@mui/icons-material/Logout";
import MenuIcon from "@mui/icons-material/Menu";
import AppBar from "@mui/material/AppBar";
import Container from "@mui/material/Container";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Toolbar from "@mui/material/Toolbar";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import useMediaQuery from "@mui/material/useMediaQuery";
import { useTheme } from "@mui/material/styles";
import { useState } from "react";
import { Link as RouterLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * Each nav entry owns the path prefixes that should keep it highlighted, so
 * the unit editor still reads as "Roster" and a game still reads as "Play".
 */
const NAV = [
  { label: "Roster", to: "/roster", matches: ["/roster", "/units", "/library"] },
  { label: "Play", to: "/lobby", matches: ["/lobby", "/games"] },
  { label: "Admin", to: "/admin", matches: ["/admin"], adminOnly: true },
];

export function Layout() {
  const { player, logout } = useAuth();
  const { pathname } = useLocation();
  const theme = useTheme();
  const wide = useMediaQuery(theme.breakpoints.up("md"));
  const [drawerOpen, setDrawerOpen] = useState(false);

  const entries = NAV.filter((entry) => !entry.adminOnly || player?.is_admin);
  // `false` tells Tabs that nothing is selected, rather than falling back to 0.
  const current =
    entries.find((entry) => entry.matches.some((p) => pathname.startsWith(p)))?.to ?? false;

  return (
    <>
      <AppBar position="sticky">
        <Toolbar sx={{ gap: 1 }}>
          {player && !wide && (
            <IconButton
              edge="start"
              color="inherit"
              aria-label="Open navigation"
              onClick={() => setDrawerOpen(true)}
            >
              <MenuIcon />
            </IconButton>
          )}
          <Typography
            variant="h6"
            component={RouterLink}
            to="/"
            sx={{
              flexGrow: 1,
              color: "inherit",
              textDecoration: "none",
              fontWeight: 700,
              letterSpacing: "0.03em",
            }}
          >
            QuickHammer
          </Typography>
          {player && wide && (
            <Tabs value={current} textColor="inherit" indicatorColor="secondary">
              {entries.map((entry) => (
                <Tab
                  key={entry.to}
                  value={entry.to}
                  label={entry.label}
                  component={RouterLink}
                  to={entry.to}
                />
              ))}
            </Tabs>
          )}
          {player && (
            <Tooltip title={`Log out ${player.name}`}>
              <IconButton color="inherit" aria-label="Log out" onClick={logout}>
                <LogoutIcon />
              </IconButton>
            </Tooltip>
          )}
        </Toolbar>
      </AppBar>

      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <List sx={{ minWidth: 220 }}>
          {entries.map((entry) => (
            <ListItemButton
              key={entry.to}
              component={RouterLink}
              to={entry.to}
              selected={current === entry.to}
              onClick={() => setDrawerOpen(false)}
            >
              <ListItemText primary={entry.label} />
            </ListItemButton>
          ))}
        </List>
      </Drawer>

      <Container component="main" maxWidth="md" sx={{ flex: 1, py: 2 }}>
        <Outlet />
      </Container>
    </>
  );
}
