"""Vercel entry point: Vercel detects this FastAPI app and routes every request to it."""

from app.main import app  # noqa: F401
