"""Phase 2 placeholder — detailed itinerary editing."""

from fastapi import APIRouter

router = APIRouter(prefix="/itinerary", tags=["itinerary"])


@router.get("/ping")
async def ping():
    return {"status": "phase-2"}
