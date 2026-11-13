"""Entry point for uvicorn: python -m uvicorn server.main:app --port 8000

Loads .env from the repo root once, before the app is imported. The server package
itself never calls load_dotenv, so tests stay independent of a local .env file.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

from server.app import app  # noqa: E402

__all__ = ["app"]
