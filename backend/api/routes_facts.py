# path: backend/api/routes_facts.py
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import ORJSONResponse

router = APIRouter()

def _get_context(window_hours: int) -> Dict[str, Any]:
    try:
        from ..services.facts_service import FactsService  # type: ignore
    except Exception as e:
        # Deterministic empty context if service unavailable
        return {"labs": [], "vitals": [], "meds": [], "notes": [], "images": []}
    svc = FactsService.instance()
    return svc.get_context(window_hours=window_hours)

@router.get(
    "/facts/context",
    response_class=ORJSONResponse,
    summary="Return labs/vitals/meds/notes/images within the window (default 72h)",
)
async def facts_context(window: int = Query(72, ge=1, le=168, description="Window in hours (1–168)")):
    try:
        return _get_context(window_hours=window)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context fetch failed: {e}") from e
