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
.venv\Scripts\python.exe -m alembic upgrade head           # migrate (also runs on startup)
python ..\scripts\make_admin.py <name>                     # grant admin (any CWD, any Python)
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

Game rules implemented so far — **Command phase only** (10th edition), in `services/unit_state.py` (pure) plus `services/game_flow.py` (phase side effects):

- Entering a player's Command phase grants them 1 CP and clears Battle-shock on their units (`begin_command_phase`, called from both `start_game` and `advance`).
- Live unit condition lives on `GameUnit` as **losses, not remainders** (`models_lost`, `wounds_lost` on the lead model only), so 0 always means undamaged and migrations stay trivial. `POST /{code}/units/{id}/damage` takes signed wounds; negative heals and doubles as undo. Owner-only, mirroring removing your own models at the table.
- Below Half-strength is **asymmetric on purpose**: single-model units qualify at *half or more wounds lost*, multi-model units at *fewer than half models remaining*, so 5 of 10 is not below half but 4 of 10 is. Tests pin both boundaries.
- Battle-shock is a 2D6 Leadership test the **player enters manually** — the app never rolls dice. `POST /{code}/units/{id}/battle-shock` requires the Command phase, the active player, the unit's owner, a below-half non-destroyed unit, and no prior test that round (`shock_tested_round`).

**Shooting phase** (`services/attack_roll.py` pure, `routers/shooting.py` API) — real dice, rolled server-side:

- An attack is a **set of weapons**, not one: a model fires all its non-pistol ranged weapons at once, must choose *either* pistols *or* everything else, and MONSTER/VEHICLE ignore that restriction. Enforced by `weapon_selection_error` in `services/combat.py`, which needs `Unit.keywords` (imported from the datasheet) and the weapon `Pistol` keyword (already imported).
- `Weapon.carrier_count` is how many models carry a weapon, **0 meaning all**. How many models fire depends **only on the attacking unit** — `resolve_shooting` takes `attacker_models` explicitly for this reason. A bug once read it from the target, so a lone character firing at a nine-model squad rolled nine times; the tests that should have caught it used the same model count for both units and a `carriers=1` default, which hid it. **Give the attacker and target different model counts in any test that touches attack volume.**
- The RNG is injected into `resolve_shooting` so tests seed it and assert exact dice. Rolling happens **server-side** and the payload is stored in `attack_rolls`, so a refresh cannot re-roll. Rolling spends the shot; **discarding is a full undo and returns it**, which does allow a deliberate re-roll — that is a trust question the app intentionally does not police.
- `allocate_damage` is **deliberately not** `unit_state.apply_wounds`: each failed save hits the lead model separately and **excess damage is lost rather than spilling**, which `apply_wounds` (a net-total cascade for manual tracking) does not do. Never swap one for the other.
- Confirming writes to the **opponent's** unit, the one place that happens. Manual `/damage` stays owner-only; here the stored dice are the record of why.
- `GameOut.pending_attack_id` announces an unconfirmed roll so the defender can open the same dice, without putting them in the 2.5s poll.
- `CombatPage` is phase-aware: in Shooting it lists ranged weapons and offers the roll, in Fight it lists melee weapons and offers only the odds. The rolled endpoints reject anything outside the Shooting phase, so the UI must not offer the roll elsewhere.

Not implemented: the Fight phase (this service should serve it, plus the one-melee-profile rule and Extra Attacks), objectives/VP, Stratagems and CP spending, Desperate Escape, army rules like Oath of Moment, cover and modifiers, BLAST/DEVASTATING WOUNDS/FEEL NO PAIN, range and line of sight, and re-rolls.

Per-game armies: a player picks ONE faction and 1+ of their units of that faction before readying up (`POST /{code}/army` with `unit_ids`; faction is derived from the units and mixing factions is a 422). Selections live in the `game_units` table via `GamePlayer.army`; replacing a selection must `db.delete` + `db.flush()` the old rows before inserting, or the unique constraint trips. The polled game state carries light summaries (`army`, `army_points`, `faction`); `GET /{code}/armies` returns full `UnitOut` data and is what CombatPage uses — only fielded units are selectable in combat, not whole rosters. Armies are locked once the game leaves lobby, and deleting a unit removes it from armies via the `Unit.game_entries` cascade.

Combat math is isolated in `backend/app/services/combat.py` as pure functions with no framework or DB imports — extend keywords/rules there and unit-test in `tests/test_combat.py`. The `/api/combat/resolve` router only loads ORM rows and maps them to `AttackerProfile`/`DefenderProfile` dataclasses. Results are expected values (not dice rolls) returned as a labeled step list the UI renders verbatim.

Unit library: `/api/library` (router `library.py`) proxies the public OpenHammer datasheet API server-side (base URL/edition in `config.py`, no auth, browser never calls it directly). `services/library.py` holds the pure OpenHammer→QuickHammer mapping (string stats like `'3+'`/`'-1'`/`'Melee'`/`BS 'N/A'` → our ints, values clamped to schema bounds, invalid dice notation falls back to `"1"`); test mapping changes in `tests/test_library.py` against the trimmed real payloads there. Import creates the unit for the current player and the frontend then opens it in the normal editor.

Auth is intentionally dependency-free (`backend/app/auth.py`): PBKDF2 password hashes and HMAC-signed `"<player_id>.<signature>"` tokens using `QH_SECRET_KEY`. Routers guard endpoints with the `get_current_player` dependency.

Data conventions that cross layers:

- Weapon `attacks` and `damage` are dice-notation strings (`"2"`, `"D6"`, `"2D6+1"`), parsed by `parse_dice` and validated at save time by a `WeaponIn` validator.
- AP is stored as a non-negative int (2 means AP-2). The unit editor displays it in 40k notation (0 to -6) and converts.
- Weapon keywords are a comma-separated string in the DB column, a `list[str]` everywhere else; `WeaponOut` has a before-validator doing the split. Only SUSTAINED HITS, LETHAL HITS, and TORRENT (auto-hit, disables crit keywords) affect the math; others are echoed back as ignored in result notes.
- Save characteristics use "roll needed" ints (3 means 3+); `invuln_save` is nullable.

Schema changes go through **Alembic** (`backend/alembic/`), never `create_all` and never by wiping the DB — production holds real accounts, rosters and uploads. Workflow:

```powershell
cd backend
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "what changed"   # then REVIEW it
.venv\Scripts\python.exe -m alembic upgrade head
```

Non-obvious rules learned the hard way:

- **Autogenerate emits `NOT NULL` columns without a `server_default`**, which fails on any table that already has rows. Add `server_default` to every non-nullable column you add.
- `env.py` sets `render_as_batch=True` because SQLite cannot alter columns in place; without it, drops/renames/type changes fail.
- `0001_baseline` is deliberately **idempotent** (creates only missing tables, adds the four pre-Alembic columns if absent) because the app was deployed before Alembic existed. That is why startup needs no stamping. Never edit a historical revision to match current models.
- `run_migrations()` in `database.py` builds the Alembic config in code with `script_location` resolved from `__file__`, so it works from any CWD and at `/app` in the container. It must never call `create_all`: the models run ahead of the baseline and would create future columns too early.
- Tests set `QH_SKIP_MIGRATIONS=1` in `tests/conftest.py` and build their own schema with `create_all`; `tests/test_migrations.py` covers real upgrades in a subprocess against empty, pre-armies, and current databases.

Lobby and deletion: `GET /api/games` lists joinable and running games (newest first, **finished ones excluded** — only the admin view shows those), with server-computed `is_member` / `can_join` / `can_delete` flags so the UI never re-derives authorisation. There is no join-by-code form; players join from the list. `Game.creator_player_id` exists so lobby deletion is authorised explicitly rather than inferred from join order, and revision `0004` backfills it from `turn_order 0`.

`services/deletion.py` owns teardown for both the creator-delete and the admin panel, and **must** be used rather than a bare `db.delete`. SQLite does not enforce foreign keys, so a partial delete leaves rows pointing at nothing and only explodes later when a game is serialized. It clears `attack_rolls` explicitly (two FKs to `game_units` make a relationship cascade ambiguous), nulls `Game.active_player_id`, drops memberships, then deletes the player, and finally removes any game left with no players. Admins cannot delete their own account.

Admin: `Player.is_admin` gates `/api/admin/*` (routers/admin.py, `require_admin` dependency in auth.py) and the frontend Admin tab. Rights are granted only from a console via the location-independent launcher: `python scripts/make_admin.py <name>` (`--revoke`, `--list`) — works from any CWD and any Python (bootstraps the backend venv, chdirs to the package root so `.env`/SQLite paths resolve); same command inside the container. New console scripts follow this pattern: implementation as a module under `backend/app/`, thin bootstrap launcher in root `scripts/` (copied into the image by the Dockerfile).

Uploads: unit pictures land in `uploads/` at the repo root (`QH_UPLOAD_DIR`, default `../uploads` relative to `backend/`), served by FastAPI at `/uploads`; the DB stores only the URL path.

API tests (`tests/test_api.py`) run against an in-memory SQLite via a `get_db` dependency override — they never touch the real DB file.

Deployment: a single multi-stage image (root `Dockerfile`) where FastAPI also serves the built React app — `QH_STATIC_DIR` mounts `SPAStaticFiles` (404 → index.html fallback for client routes) at `/`, empty in dev. All persistent state (SQLite DB + uploads) lives in the `/data` volume. The user builds and pushes the image manually, runs it on Unraid (port 8000, `/mnt/user/appdata/quickhammer` → `/data`, `QH_SECRET_KEY` env), with a Cloudflare Tunnel providing `https://quickhammer.<domain>`; steps are in README "Deployment". No DB migrations exist: a `models.py` change is a breaking update in production (planned: Alembic).
