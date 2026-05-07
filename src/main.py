import sys
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

# Keep `python src/main.py` working while preserving package imports for ASGI.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn
from fastapi import FastAPI, Request
from langfuse import observe

from src.api.routes import chunking, health  # noqa: E402
from src.core.logger import get_logger  # noqa: E402

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

    @app.middleware("http")
    @observe(name="fastapi-request")
    async def log_http_request(request: Request, call_next):
        """Trace and log every FastAPI request."""
        start_time = perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((perf_counter() - start_time) * 1000, 2)
            logger.error(
                "HTTP request failed",
                extra={
                    "component": "http",
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "error_type": type(exc).__name__,
                },
                exc_info=True,
            )
            raise

        duration_ms = round((perf_counter() - start_time) * 1000, 2)
        logger.info(
            "HTTP request completed",
            extra={
                "component": "http",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    # Register routers
    app.include_router(chunking.router)
    app.include_router(health.router)

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
