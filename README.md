# QuickHammer

A responsive web companion for tabletop Warhammer 40k. Works on laptop, iPad, and phone.

Players create a profile, build a unit roster, pick a game from a list, and step through the five
phases of a 10th-edition turn together. The app tracks casualties, resolves the Command phase, and
rolls shooting attacks with real dice, showing every die and its outcome before you apply the result.
Rosters can be filled by hand or imported from official datasheets via the public OpenHammer API,
searchable by name and faction.

## Stack

- **Frontend:** React + TypeScript (Vite), Material UI (dark theme), mobile-first
- **Backend:** Python 3 + FastAPI, SQLite via SQLAlchemy, Alembic migrations
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
The SQLite database (`quickhammer.db`) and `uploads/` folder are created automatically, and the
schema is migrated on startup, so there is no separate setup step.

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
.venv\Scripts\python.exe -m pytest -q          # everything
.venv\Scripts\python.exe -m pytest tests/test_attack_roll.py -q   # one file
```

Tests build their own in-memory database and never touch `quickhammer.db`.

### Changing the database schema

Every change is an Alembic revision, so deployed data survives. Never delete the database.

```powershell
cd backend
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "what changed"
.venv\Scripts\python.exe -m alembic upgrade head
```

Read the generated file before committing it. Autogenerate writes `NOT NULL` columns without a
default, which fails on any table that already has rows, so add a `server_default` to each one.

## Project layout

```
Dockerfile            Multi-stage: builds the frontend, serves it from FastAPI
docker-compose.yml    Local run, mirrors the Unraid container settings
scripts/
  make_admin.py       Grant/revoke admin from any directory

backend/
  alembic/            Migrations; every schema change is a revision here
  app/
    main.py           FastAPI app: CORS, routers, static uploads + built frontend
    config.py         Settings (.env)
    database.py       Engine, session, and the startup migration runner
    models.py         Player, Unit, Weapon, Game, GamePlayer, GameUnit, AttackRoll
    schemas.py        Pydantic request/response models
    auth.py           Password hashing + signed tokens
    make_admin.py     Admin CLI implementation (run via scripts/make_admin.py)
    routers/          players, units, games, shooting, combat, library, admin
    services/
      combat.py       Expected-value math + weapon-selection rules
      attack_roll.py  Rolled shooting: real dice, per-die outcomes, allocation
      unit_state.py   Casualties, Below Half-strength, Battle-shock tests
      game_flow.py    Phase order, turn progression, command points
      library.py      OpenHammer datasheet -> QuickHammer mapping
      deletion.py     Tearing down games and players without orphan rows
  tests/
frontend/
  src/
    theme.ts          MUI theme: stock dark palette + 44px touch targets
    api/              fetch client + shared types
    context/          auth state
    hooks/            usePolling, useConfirm (promise-based confirm Dialog)
    components/       Layout, NumberField, UnitCard, PhaseTracker,
                      ArmySelector, ArmyStatusPanel, CommandPhasePanel,
                      DiceRollTrack, DiceMathBreakdown
    pages/            Login, Roster, UnitEditor, Library, Lobby, Game,
                      Combat, AttackView, Admin
uploads/              Unit pictures (gitignored; the /data volume in production)
```

## Game flow

1. Register / log in (name + password)
2. Build units in **Roster**: import official datasheets from the unit library
   (search + faction filter), or create/edit units manually (statline, weapons, picture upload)
3. **Play**: create a game, or pick one from the list and hit Join. Finished games are hidden,
   and the player who opened a game can delete it while it is still Pending.
4. In the waiting room, pick the army you are fielding: one faction, then one or more
   of its units. Confirm it, then Ready up.
5. Once every player has an army and has readied up, **Start game** lights up. Any player can
   press it — there is no host — and nobody is dropped into round 1 unexpectedly. Until then the
   button is greyed out and names whoever is still holding things up. Phases per player turn:
   Command → Movement → Shooting → Charge → Fight
6. Record casualties on your own units as they happen, using the **Your army** panel.
7. In your **Command phase** you gain a Command Point, any Battle-shock on your units wears
   off, and every unit below half strength must take a Battle-shock test. Roll 2D6 on the table
   and type the total; the app applies the result and tracks the consequences.
8. In your **Shooting phase**, pick a unit, a target, and which weapons fire. A model fires all its
   non-pistol ranged weapons together, or its pistols instead, and Monsters and Vehicles may fire
   everything at once. **Preview odds** shows the averages; **Roll to hit** rolls real dice and
   shows every one with its outcome (Miss, Hit, Wounded, Saved, Destroyed). Then **Confirm and
   apply** writes the damage to the target and returns you to the game, or **Discard** throws the
   result away and gives the unit its shot back. Each unit shoots once per phase, and the dice are
   rolled on the server so a refresh cannot re-roll them.
9. The Fight phase has no rolled dice yet. The same screen switches to your melee weapons and
   works out the odds, so you roll at the table and record the casualties yourself.

Throughout, only units fielded for that game are selectable, and destroyed units are greyed out.
Your opponent can watch your dice from their own device while an attack is waiting to be confirmed.

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
games with their status (Pending / Running / Done), including finished games that are
hidden from the Play page. Admins can delete users and games from there. Deleting a user
removes their roster and their place in every game, but games keep running for the
remaining players. Admins cannot delete their own account.

## Status & roadmap

### Working today

**Rosters** — profiles, manual unit editing, picture upload, OpenHammer datasheet import,
grouping by faction with points totals per faction and per unit.

**Games** — browse and join from a list, pick one faction and the units you are fielding,
ready up and start the match on an explicit press by any player, phase and turn tracking for 2 to
4 players, casualty tracking.

**Rules** — the **Command phase** in full (command points, Below Half-strength, Battle-shock
tests from your own 2D6 roll) and the **Shooting phase** in full (multi-weapon volleys, the
Pistol restriction with the Monster and Vehicle exception, per-weapon carrier counts, real
server-rolled dice with per-die outcomes, confirm or discard). Weapon keywords SUSTAINED HITS,
LETHAL HITS and TORRENT affect both the rolled and the expected-value paths.

**Operations** — admin view with user and game deletion, Docker deployment behind a Cloudflare
Tunnel, and Alembic migrations that upgrade a live database in place.

### Not built yet

Rough priority order.

#### In-game features
- Rules for the Fight phase, then Movement and Charge
- Objective markers and victory points
- Stratagems and spending command points
- More weapon keywords (DEVASTATING WOUNDS, BLAST, RAPID FIRE, ANTI-X…)
- Hit and wound modifiers, and cover
- Rolled dice for melee, reusing the shooting resolver
- Feeding a rolled result into casualty tracking without the confirm step

#### Web-app features
- Password reset
- A game log, so players can review what happened
- Range and line-of-sight checks (needs a notion of board position)
