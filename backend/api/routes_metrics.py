# path: backend/api/routes_metrics.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import ORJSONResponse

router = APIRouter()


@router.get("/health", response_class=ORJSONResponse, summary="Liveness probe (offline)")
def health() -> Dict[str, Any]:
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@router.get(
    "/metrics/session",
    response_class=ORJSONResponse,
    summary="Return session metrics: timers, keystrokes, chip_counts",
)
def metrics_session() -> Dict[str, Any]:
    try:
        from ..services.audit_metrics import MetricsService  # type: ignore
        return MetricsService.instance().session_snapshot()
    except Exception:
        # Deterministic stub (no external calls)
        return {
            "timers": {"decode_ms": 0, "extract_ms": 0, "compose_ms": 0},
            "keystrokes": 0,
            "chip_counts": {"A": 0, "B": 0, "C": 0, "D": 0},
        }
