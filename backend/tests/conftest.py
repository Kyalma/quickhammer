"""Test-wide setup.

Tests build their own in-memory schema with Base.metadata.create_all, so the
app's startup hook must not run Alembic or touch the real database file. This
must be set before app.config caches its settings.
"""
import os

os.environ["QH_SKIP_MIGRATIONS"] = "1"
