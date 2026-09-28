"""QuickHammer API entry point."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import get_settings
from .database import init_db
from .routers import admin, combat, games, library, players, units


class SPAStaticFiles(StaticFiles):
    """Serve the built React app; unknown paths fall back to index.html so
    client-side routes like /roster survive a page refresh. API paths keep
    their real 404s. Starlette signals a missing file by raising (newer
    versions) or returning a 404 response (older ones) — handle both."""

    @staticmethod
    def _is_app_route(path: str) -> bool:
        # StaticFiles hands us an OS-normalized path (backslashes on Windows).
        normalized = path.replace("\\", "/").lstrip("/")
        return not normalized.startswith(("api/", "uploads/"))

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and self._is_app_route(path):
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and self._is_app_route(path):
            return await super().get_response("index.html", scope)
        return response


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
app.include_router(admin.router)

# Unit pictures.
app.mount("/uploads", StaticFiles(directory=get_settings().upload_path), name="uploads")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# Production: serve the built React app (see Dockerfile). Mounted last so the
# API routes and /uploads always win. In development this is skipped and Vite
# serves the frontend.
_static = get_settings().static_dir
if _static and Path(_static).is_dir():
    app.mount("/", SPAStaticFiles(directory=_static, html=True), name="frontend")
