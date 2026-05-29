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

# Avoid FileHandler initialization against the deployed source tree on Vercel.
# Runtime logs should go to stdout/stderr in serverless environments.
if os.getenv("VERCEL") == "1":
    logging.basicConfig = lambda *args, **kwargs: logging.getLogger().setLevel(kwargs.get("level", logging.INFO))

from app import app  # noqa: E402,F401
