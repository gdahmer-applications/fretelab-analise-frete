"""Vercel Python entrypoint for FreteLab.

Vercel expects Python Serverless Functions inside the api/ directory.
This wrapper imports the Flask app instance from the project root.
"""
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app  # noqa: E402,F401
