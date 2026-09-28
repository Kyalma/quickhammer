#!/usr/bin/env python3
"""Grant or revoke QuickHammer admin rights. Runnable from ANY directory:

    python scripts/make_admin.py <player-name>
    python scripts/make_admin.py --list
    python scripts/make_admin.py <player-name> --revoke

Inside the Docker container (Unraid: container icon -> Console):

    python scripts/make_admin.py <player-name>

The bootstrap below locates the backend package next to this script (repo
layout `../backend/app` or container layout `../app`), re-runs itself with the
backend venv's Python if the current interpreter lacks the dependencies, and
switches into the backend directory so `.env` and the default SQLite path
resolve exactly as they do for the server.
"""
import os
import subprocess
import sys
from pathlib import Path


def _package_root() -> Path:
    here = Path(__file__).resolve().parent
    for candidate in (here.parent / "backend", here.parent):
        if (candidate / "app" / "__init__.py").is_file():
            return candidate
    sys.exit("Could not find the QuickHammer backend package next to this script.")


def _ensure_dependencies(root: Path) -> None:
    """If this interpreter can't import the app, delegate to the backend venv."""
    try:
        import sqlalchemy  # noqa: F401

        return
    except ImportError:
        pass
    for venv_python in (root / ".venv/Scripts/python.exe", root / ".venv/bin/python"):
        if venv_python.is_file() and venv_python != Path(sys.executable).resolve():
            raise SystemExit(
                subprocess.call([str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]])
            )
    sys.exit(
        "Dependencies are not installed and no venv was found at backend/.venv.\n"
        "Run: cd backend && python -m venv .venv && .venv\\Scripts\\pip install -r requirements.txt"
    )


_root = _package_root()
_ensure_dependencies(_root)
os.chdir(_root)  # .env and sqlite:///./quickhammer.db resolve like the server's
sys.path.insert(0, str(_root))

from app.make_admin import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
