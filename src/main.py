from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import health
from core.config import settings
from core.logger import get_logger

# Initialize logger
logger = get_logger("bootstrap")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan context manager for the FastAPI application."""
    logger.info(
        "Application startup complete",
        extra={
            "component": "bootstrap",
            "project_name": "InsureVN",
            "status": "started",
        },
    )
    yield
    logger.info(
        "Application shutdown initiated",
        extra={
            "component": "bootstrap",
            "project_name": "InsureVN",
            "status": "stopped",
        },
    )


def create_app() -> FastAPI:
    """Application factory for the InsureVN FastAPI service."""
    app = FastAPI(
        title="InsureVN API",
        description="Multi-agent AI system for the Vietnamese insurance industry",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Register routers
    app.include_router(health.router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
