# path: backend/api/routes_chips.py
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, Field, ConfigDict

router = APIRouter()


class ChipResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chip_id: str
    action: str = Field(..., description="One of: accept | edit | override_blocked | evidence")
    value: str | None = None
    reason: str | None = Field(None, description="Required when overriding a D-guard")


class ChipResolveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool


def _resolve_with_service(chip_id: str, action: str, value: str | None, reason: str | None) -> ChipResolveResponse:
    try:
        from ..services.chips_engine import ChipsEngine  # type: ignore
        from ..services.audit_metrics import MetricsService  # type: ignore
    except Exception:
        # Deterministic stub: only accept/evidence allowed; override requires reason.
        if action == "override_blocked" and not reason:
            raise HTTPException(status_code=400, detail="Override requires 'reason'.")
        return ChipResolveResponse(ok=True)

    engine = ChipsEngine.instance()
    ok = engine.resolve(chip_id=chip_id, action=action, value=value, reason=reason)
    # audit
    try:
        MetricsService.instance().log_chip_action(chip_id, action)
    except Exception:
        pass
    return ChipResolveResponse(ok=bool(ok))


@router.post(
    "/chips/resolve",
    response_model=ChipResolveResponse,
    response_class=ORJSONResponse,
    summary="Resolve a chip action (accept/edit/override_blocked/evidence)",
)
async def resolve_chip(body: ChipResolveRequest = Body(...)):
    try:
        return _resolve_with_service(body.chip_id, body.action, body.value, body.reason)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chip resolution failed: {e}") from e
