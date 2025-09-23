# path: backend/api/__init__.py
"""
API package: exposes a top-level router that aggregates all route groups.
"""
from fastapi import APIRouter

from .routes_asr import router as asr_router
from .routes_extract import router as extract_router
from .routes_compose import router as compose_router
from .routes_planpack import router as planpack_router
from .routes_chips import router as chips_router
from .routes_metrics import router as metrics_router
from .routes_facts import router as facts_router  # NEW

api_router = APIRouter()
api_router.include_router(metrics_router, tags=["system"])
api_router.include_router(facts_router, tags=["facts"])      # NEW
api_router.include_router(asr_router, tags=["asr"])
api_router.include_router(extract_router, tags=["extract"])
api_router.include_router(compose_router, tags=["compose"])
api_router.include_router(planpack_router, tags=["planpack"])
api_router.include_router(chips_router, tags=["chips"])
