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

## Status & roadmap

Working today: profiles, roster with picture upload, OpenHammer datasheet import,
game sessions (create / join / ready / auto-start), phase & turn tracking for 2–4 players,
and the expected-value combat resolver with SUSTAINED HITS, LETHAL HITS, and TORRENT support.

Not built yet (ideas, in rough priority order):

- Wound / casualty tracking on units during a game
- Dice-roll mode (actual rolls instead of expected values)
- More weapon keywords (DEVASTATING WOUNDS, BLAST, RAPID FIRE, ANTI-X…)
- Points display / army list totals
- Password reset, HTTPS, deployment
