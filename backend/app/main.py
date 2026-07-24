from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.init_db import init_db


def create_app(initialize_database: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if initialize_database:
            init_db()
        yield

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "AI career assistant for job auditing, resume review, matching, "
            "and interview practice."
        ),
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health", tags=["system"])
    def health_check():
        return {
            "status": "ok",
            "service": settings.app_name,
            "environment": settings.environment,
        }

    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
