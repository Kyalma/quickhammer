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
3. **Lobby**: create a game (get a join code) or join with a code, then Ready up
4. When everyone is ready the game starts. Phases per player turn:
   Command → Movement → Shooting → Charge → Fight
5. In Shooting / Fight, open the **Combat** resolver: pick your unit + weapon vs an enemy unit
   and get the full expected-value breakdown (hits → wounds → failed saves → damage → models slain)

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

> Adding new columns is safe: startup applies additive migrations automatically
> (see `_MIGRATION_COLUMNS` in `backend/app/database.py`). Bigger schema changes
> (renames, drops) still need a real migration plan before shipping.

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

Working today: profiles, roster with picture upload, OpenHammer datasheet import,
game sessions (create / join / ready / auto-start), phase & turn tracking for 2–4 players,
and the expected-value combat resolver with SUSTAINED HITS, LETHAL HITS, and TORRENT support.

Not built yet (ideas, in rough priority order):

### In-game features
- Wound / casualty tracking on units during a game
- Dice-roll mode (actual rolls instead of expected values)
- More weapon keywords (DEVASTATING WOUNDS, BLAST, RAPID FIRE, ANTI-X…)
- Points display / army list totals

### Web-app features
- Password reset, HTTPS, deployment
