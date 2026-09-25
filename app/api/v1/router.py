"""API v1 router."""

from fastapi import APIRouter

from app.api.v1 import auth, chat, destinations, itinerary, trips

router = APIRouter()
router.include_router(auth.router)
router.include_router(trips.router)
router.include_router(itinerary.router)
router.include_router(destinations.router)
router.include_router(chat.router)
