"""Vercel Python entrypoint for FreteLab.

Vercel expects Python Serverless Functions inside the api/ directory.
This wrapper imports the Flask app instance from the project root.
"""
from pathlib import Path
import logging
import os
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if os.getenv("VERCEL") == "1":
    # Vercel serverless functions should log to stdout/stderr, not to a file
    # inside the deployed source directory.
    logging.basicConfig = lambda *args, **kwargs: logging.getLogger().setLevel(kwargs.get("level", logging.INFO))

    # Some legacy app modules create local folders during import. On Vercel the
    # source tree may be read-only, so ignore mkdir failures during cold start.
    _original_mkdir = Path.mkdir

    def _safe_mkdir(self, mode=0o777, parents=False, exist_ok=False):
        try:
            return _original_mkdir(self, mode=mode, parents=parents, exist_ok=exist_ok)
        except OSError:
            return None

    Path.mkdir = _safe_mkdir

from app import app  # noqa: E402,F401
