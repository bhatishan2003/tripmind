"""Phase 2 placeholder — conversational trip chat."""

from fastapi import APIRouter

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/ping")
async def ping():
    return {"status": "phase-2"}
