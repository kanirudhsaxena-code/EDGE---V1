"""Database helpers for EDGE V1.

Production uses PostgreSQL/Neon. Credentials are supplied only through
environment variables and must never be committed.
"""
import os

def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return url
