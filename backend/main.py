# path: backend/main.py
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from .config import load_config, setup_logging, enforce_offline
from .api import api_router


log = logging.getLogger("m1")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Startup: ensure data dirs, initialize light services to prove readiness.
    Shutdown: NOP (services clean up on process exit).
    """
    # Startup
    cfg = app.state.cfg
    # Ensure local data folders exist
    for d in ("data", "data/audit", "models", "models/asr", "models/llm"):
        Path(d).mkdir(parents=True, exist_ok=True)

    # Optional warm-ups (guarded: services may be stubs right now)
    try:
        from .services.facts_service import FactsService

        FactsService.instance()  # init DB/FTS
    except Exception as e:
        log.warning("FactsService init failed (stub will be used): %s", e)

    try:
        from .db.repo import Repo

        Repo()  # ensure full schema (including triggers)
    except Exception as e:
        log.warning("Repo init failed: %s", e)

    log.info("M1 backend started (offline=%s)", cfg.get("privacy", {}).get("offline_only", True))
    yield
    # Shutdown
    log.info("M1 backend shutting down.")


def create_app() -> FastAPI:
    setup_logging()
    cfg = load_config()
    enforce_offline(cfg)

    app = FastAPI(
        title="MinuteOne (M1)",
        version="0.1.0",
        default_response_class=ORJSONResponse,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.cfg = cfg  # expose config to routes/services if needed
    app.include_router(api_router, prefix="")
    return app


# ASGI app
app = create_app()


if __name__ == "__main__":
    # Local run: 127.0.0.1 only (offline-by-default)
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8011, reload=False, log_level="info")
