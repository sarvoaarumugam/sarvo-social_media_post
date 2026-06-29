"""Project entrypoint. Kept thin and at the repo root (next to .env).

Run (dev):   uv run uvicorn main:app --reload
or:          uv run python main.py
"""

import uvicorn

from app.application import create_app
from app.core.config import get_settings

app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
