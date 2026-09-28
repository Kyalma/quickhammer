# QuickHammer

A responsive web companion for tabletop Warhammer 40k. Works on laptop, iPad, and phone.

Players create a profile, build their unit roster (statlines, weapons, a picture), join a shared
game session by code, follow the five game phases together, and resolve shooting / fight math
automatically with the A-vs-B combat resolver. Rosters can be filled by hand or imported from
official datasheets via the public OpenHammer API (searchable by name and faction).

## Stack

- **Frontend:** React + TypeScript (Vite), plain CSS, mobile-first
- **Backend:** Python 3 + FastAPI, SQLite via SQLAlchemy
- **Live sync:** clients poll the game-state endpoint every few seconds

## Getting started

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then edit SECRET_KEY
python -m uvicorn app.main:app --reload
```

> Use `python -m uvicorn` rather than `uvicorn` directly: Windows Application Control
> (Smart App Control) can block the unsigned `uvicorn.exe` shim in the venv, while
> `python.exe` is signed and runs fine.

API runs at http://localhost:8000 (interactive docs at http://localhost:8000/docs).
The SQLite database (`quickhammer.db`) and `uploads/` folder are created automatically.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

App runs at http://localhost:5173. The dev server proxies `/api` and `/uploads` to the backend,
so start the backend first. To try it from an iPad/phone on the same network, run
`npm run dev -- --host` and open `http://<your-pc-ip>:5173`.

### Tests

```powershell
cd backend
pytest
```

## Project layout

```
backend/
  app/
    main.py          FastAPI app: CORS, routers, static uploads
    config.py        Settings (.env)
    database.py      SQLAlchemy engine + session
    models.py        Player, Unit, Weapon, Game, GamePlayer
    schemas.py       Pydantic request/response models
    auth.py          Password hashing + signed tokens
    routers/         players, units, games, combat, library endpoints
    services/
      combat.py      Pure combat math (hit / wound / save / damage)
      game_flow.py   Phase order and turn logic
      library.py     OpenHammer datasheet -> QuickHammer mapping
  tests/
frontend/
  src/
    api/             fetch client + shared types
    context/         auth state
    hooks/           usePolling
    components/      Layout, UnitCard, PhaseTracker, DiceMathBreakdown
    pages/           Login, Roster, UnitEditor, Library, Lobby, Game, Combat
```

## Game flow

1. Register / log in (name + password)
2. Build units in **Roster**: import official datasheets from the unit library
   (search + faction filter), or create/edit units manually (statline, weapons, picture upload)
3. **Lobby**: create a game (get a join code) or join with a code
4. In the waiting room, pick the army you are fielding: one faction, then one or more
   of its units. Confirm it, then Ready up.
5. When everyone is ready the game starts. Phases per player turn:
   Command → Movement → Shooting → Charge → Fight
6. Record casualties on your own units as they happen, using the **Your army** panel.
7. In your **Command phase** you gain a Command Point, any Battle-shock on your units wears
   off, and every unit below half strength must take a Battle-shock test. Roll 2D6 on the table
   and type the total; the app applies the result and tracks the consequences.
8. In Shooting / Fight, open the **Combat** resolver: pick your unit + weapon vs an enemy unit
   and get the full expected-value breakdown (hits → wounds → failed saves → damage → models slain).
   Only units fielded for that game are selectable, and destroyed units are greyed out.

## Deployment (Docker → Unraid → Cloudflare Tunnel)

One image serves everything: the API, uploaded pictures, and the built React app.
All user data (SQLite DB + pictures) lives in the `/data` volume — that folder is the backup.

### 1. Build and push the image

```powershell
docker build -t <dockerhub-user>/quickhammer:latest -t <dockerhub-user>/quickhammer:v1 .
docker push <dockerhub-user>/quickhammer:latest
docker push <dockerhub-user>/quickhammer:v1
```

Tag a version alongside `latest` each time — rolling back on Unraid is then just switching the tag.

To try it locally first:

```powershell
$env:QH_SECRET_KEY = "<long random string>"; docker compose up --build
# open http://localhost:8000
```

### 2. Add the container on Unraid

Docker tab → **Add Container**:

| Setting | Value |
|---|---|
| Repository | `<dockerhub-user>/quickhammer:latest` |
| Port | host `8040` (any free port) → container `8000` (fixed) |
| Path | host `/mnt/user/appdata/quickhammer` → container `/data` |
| Variable | `QH_SECRET_KEY` = a long random string |

`QH_SECRET_KEY` signs the login tokens. Generate it once (e.g. `openssl rand -hex 32`)
and never change it, or every player gets logged out.

### 3. Cloudflare Tunnel

1. Cloudflare dashboard → Zero Trust → Networks → Tunnels → **Create a tunnel** (Cloudflared), copy the token.
2. On Unraid, install **cloudflared** from Community Apps and paste the token
   (or run `cloudflare/cloudflared:latest` with `tunnel run --token <token>`).
3. In the tunnel's **Public Hostnames**, add `quickhammer.<yourdomain>` →
   service `http://<unraid-lan-ip>:8040` (the host port you mapped, not the
   container's 8000).

Cloudflare terminates TLS and the tunnel connects outbound, so no ports are
forwarded and your home IP stays private. The app is then live at
`https://quickhammer.<yourdomain>`.

### Updating

```powershell
docker build -t <dockerhub-user>/quickhammer:latest -t <dockerhub-user>/quickhammer:v2 .
docker push <dockerhub-user>/quickhammer:latest; docker push <dockerhub-user>/quickhammer:v2
```

Then Unraid Docker tab → the container shows an update → **apply/force update**.
The `/data` volume is untouched, so accounts, rosters, and pictures survive.

> Database changes are handled by Alembic and run automatically when the container
> starts, so your data survives updates. Databases created before Alembic was added
> are upgraded in place, no manual step needed.

### Admin

Grant a player admin rights from a console. The launcher in `scripts/` works from any
directory, locally (auto-uses the backend venv) and inside the container:

```bash
# On the server (Unraid: Docker tab → container → Console, or docker exec):
docker exec -it QuickHammer python scripts/make_admin.py <player-name>
docker exec -it QuickHammer python scripts/make_admin.py --list
docker exec -it QuickHammer python scripts/make_admin.py <name> --revoke

# Local development (any directory, any Python):
python scripts/make_admin.py <player-name>
```

Admins get an **Admin** tab in the app showing all users (with unit counts) and all
games with their status (Pending / Running / Done).

## Status & roadmap

Working today: profiles, roster with picture upload grouped by faction with points totals,
OpenHammer datasheet import, game sessions (create / join / pick a faction and army / ready /
auto-start), phase & turn tracking for 2–4 players, casualty tracking, the **Command phase**
(command points and Battle-shock tests), the expected-value combat resolver with SUSTAINED HITS,
LETHAL HITS and TORRENT, an admin view, Docker deployment and Alembic migrations.

Not built yet (ideas, in rough priority order):

### In-game features
- Rules for the other four phases (Movement, Shooting, Charge, Fight)
- Objective markers and victory points
- Stratagems and spending command points
- More weapon keywords (DEVASTATING WOUNDS, BLAST, RAPID FIRE, ANTI-X…)
- Feeding combat results straight into casualty tracking
- Dice-roll mode for combat (actual rolls instead of expected values)

### Web-app features
- Password reset, HTTPS, deployment
