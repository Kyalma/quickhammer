# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

QuickHammer is a Warhammer 40k (10th edition) tabletop companion web app: player profiles, unit rosters with picture uploads, shared game sessions joined by code, phase tracking, and an A-vs-B expected-value combat calculator. React + TypeScript (Vite) frontend, Python FastAPI backend, SQLite.

Deliberate stack decisions (made with the user — do not re-propose alternatives): FastAPI + JSON REST instead of gRPC, SQLite instead of Postgres, polling instead of websockets/streaming for live sync, plain CSS with no UI framework.

The project is not under version control yet (no git repo). Feature status and the agreed roadmap live in README.md ("Status & roadmap"). An `openhammer` MCP server (same data as the proxied OpenHammer REST API) is registered in the user's local Claude config for this project and can be used to look up datasheets directly.

## Commands

Backend (from `backend/`, venv at `backend/.venv`):

```powershell
.venv\Scripts\python.exe -m pytest -q                      # all tests
.venv\Scripts\python.exe -m pytest tests/test_combat.py -q # one file
.venv\Scripts\python.exe -m pytest -q -k "lethal"          # by keyword
python -m uvicorn app.main:app --reload                    # run server (port 8000)
```

Always launch uvicorn via `python -m uvicorn`, never the bare `uvicorn` command: Windows Smart App Control blocks the unsigned `uvicorn.exe` shim in the venv.

Frontend (from `frontend/`):

```powershell
npm run dev     # dev server on 5173, proxies /api and /uploads to :8000
npm run build   # tsc --noEmit type check + vite build
```

If `npm`/`node` are not found, prepend Node to the shell PATH: `$env:Path = "$env:ProgramFiles\nodejs;$env:APPDATA\npm;$env:Path"`.

Start the backend before the frontend; there is no mocking, every page hits the real API.

## Architecture

Request path: React pages → `frontend/src/api/client.ts` (fetch wrapper adding the Bearer token from localStorage) → Vite proxy → FastAPI routers (`backend/app/routers/`) → SQLAlchemy models. Frontend types in `frontend/src/api/types.ts` are hand-written mirrors of the Pydantic schemas in `backend/app/schemas.py`; when you change one, change the other.

Game-state flow: there is no push channel. `usePolling` re-fetches `GET /api/games/{code}` every ~2.5 s on the lobby/game pages; every mutating game endpoint also returns the full serialized game state, and turn/phase progression logic lives in `backend/app/services/game_flow.py` (5 phases per player turn; after Fight, the turn passes; when the order wraps, the round increments). Ready-toggling auto-starts the game once 2+ players are all ready AND each has an army.

Per-game armies: a player picks ONE faction and 1+ of their units of that faction before readying up (`POST /{code}/army` with `unit_ids`; faction is derived from the units and mixing factions is a 422). Selections live in the `game_units` table via `GamePlayer.army`; replacing a selection must `db.delete` + `db.flush()` the old rows before inserting, or the unique constraint trips. The polled game state carries light summaries (`army`, `army_points`, `faction`); `GET /{code}/armies` returns full `UnitOut` data and is what CombatPage uses — only fielded units are selectable in combat, not whole rosters. Armies are locked once the game leaves lobby, and deleting a unit removes it from armies via the `Unit.game_entries` cascade.

Combat math is isolated in `backend/app/services/combat.py` as pure functions with no framework or DB imports — extend keywords/rules there and unit-test in `tests/test_combat.py`. The `/api/combat/resolve` router only loads ORM rows and maps them to `AttackerProfile`/`DefenderProfile` dataclasses. Results are expected values (not dice rolls) returned as a labeled step list the UI renders verbatim.

Unit library: `/api/library` (router `library.py`) proxies the public OpenHammer datasheet API server-side (base URL/edition in `config.py`, no auth, browser never calls it directly). `services/library.py` holds the pure OpenHammer→QuickHammer mapping (string stats like `'3+'`/`'-1'`/`'Melee'`/`BS 'N/A'` → our ints, values clamped to schema bounds, invalid dice notation falls back to `"1"`); test mapping changes in `tests/test_library.py` against the trimmed real payloads there. Import creates the unit for the current player and the frontend then opens it in the normal editor.

Auth is intentionally dependency-free (`backend/app/auth.py`): PBKDF2 password hashes and HMAC-signed `"<player_id>.<signature>"` tokens using `QH_SECRET_KEY`. Routers guard endpoints with the `get_current_player` dependency.

Data conventions that cross layers:

- Weapon `attacks` and `damage` are dice-notation strings (`"2"`, `"D6"`, `"2D6+1"`), parsed by `parse_dice` and validated at save time by a `WeaponIn` validator.
- AP is stored as a non-negative int (2 means AP-2). The unit editor displays it in 40k notation (0 to -6) and converts.
- Weapon keywords are a comma-separated string in the DB column, a `list[str]` everywhere else; `WeaponOut` has a before-validator doing the split. Only SUSTAINED HITS, LETHAL HITS, and TORRENT (auto-hit, disables crit keywords) affect the math; others are echoed back as ignored in result notes.
- Save characteristics use "roll needed" ints (3 means 3+); `invuln_save` is nullable.

Schema changes: `init_db()` runs `create_all()` (new tables) plus a minimal additive migration: new COLUMNS must be appended to `_MIGRATION_COLUMNS` in `backend/app/database.py` (table, column, DDL), which ALTERs existing databases on startup. Production has real user data — never instruct wiping the DB. Anything beyond adding a column (renames, drops, type changes) needs a real migration plan first.

Admin: `Player.is_admin` gates `/api/admin/*` (routers/admin.py, `require_admin` dependency in auth.py) and the frontend Admin tab. Rights are granted only from a console via the location-independent launcher: `python scripts/make_admin.py <name>` (`--revoke`, `--list`) — works from any CWD and any Python (bootstraps the backend venv, chdirs to the package root so `.env`/SQLite paths resolve); same command inside the container. New console scripts follow this pattern: implementation as a module under `backend/app/`, thin bootstrap launcher in root `scripts/` (copied into the image by the Dockerfile).

Uploads: unit pictures land in `uploads/` at the repo root (`QH_UPLOAD_DIR`, default `../uploads` relative to `backend/`), served by FastAPI at `/uploads`; the DB stores only the URL path.

API tests (`tests/test_api.py`) run against an in-memory SQLite via a `get_db` dependency override — they never touch the real DB file.

Deployment: a single multi-stage image (root `Dockerfile`) where FastAPI also serves the built React app — `QH_STATIC_DIR` mounts `SPAStaticFiles` (404 → index.html fallback for client routes) at `/`, empty in dev. All persistent state (SQLite DB + uploads) lives in the `/data` volume. The user builds and pushes the image manually, runs it on Unraid (port 8000, `/mnt/user/appdata/quickhammer` → `/data`, `QH_SECRET_KEY` env), with a Cloudflare Tunnel providing `https://quickhammer.<domain>`; steps are in README "Deployment". No DB migrations exist: a `models.py` change is a breaking update in production (planned: Alembic).
