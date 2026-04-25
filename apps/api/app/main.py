"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import (
    assembly,
    drafts,
    evidence,
    interactions,
    papers,
    planning,
    prompts,
    reviews,
    sections,
    workflows,
)
from app.db import create_db_and_tables


def create_app(*, init_database: bool = True) -> FastAPI:
    """Create the API app."""

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if init_database:
            create_db_and_tables()
        yield

    app = FastAPI(title="Paper Harness API", version="0.1.0", lifespan=lifespan)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(papers.router)
    app.include_router(interactions.router)
    app.include_router(planning.router)
    app.include_router(prompts.router)
    app.include_router(workflows.router)
    app.include_router(sections.router)
    app.include_router(evidence.router)
    app.include_router(drafts.router)
    app.include_router(reviews.router)
    app.include_router(assembly.router)
    return app


app = create_app()
