"""Phase 2 placeholder — destination search."""

from fastapi import APIRouter

router = APIRouter(prefix="/destinations", tags=["destinations"])


@router.get("/ping")
async def ping():
    return {"status": "phase-2"}
