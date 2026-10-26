"""Run with: python -m uvicorn siteforge.api:app --host 127.0.0.1 --port 8787."""
from siteforge.api import app

__all__ = ["app"]
