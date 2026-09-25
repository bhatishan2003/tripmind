"""FastAPI application entrypoint (Phase 1)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import models so they register on Base.metadata
import app.db.models
from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.database import Base, engine

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phase 1: auto-create tables for local dev. Production uses Alembic.
    if settings.ENVIRONMENT == "local":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}

    app.include_router(v1_router, prefix=settings.API_V1_PREFIX)
    return app


app = create_app()
