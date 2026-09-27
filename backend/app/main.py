"""QuickHammer API entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import init_db
from .routers import combat, games, library, players, units


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="QuickHammer", version="0.1.0", lifespan=lifespan)

# The Vite dev server proxies /api in development, but CORS is kept open for
# direct access from other devices (iPad / phone) on the local network.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router)
app.include_router(units.router)
app.include_router(games.router)
app.include_router(combat.router)
app.include_router(library.router)

# Unit pictures.
app.mount("/uploads", StaticFiles(directory=get_settings().upload_path), name="uploads")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
