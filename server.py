"""Compatibility command: uv run server.py (or python -m app)."""
from app.main import app, run

if __name__ == "__main__":
    run()
