import sys

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    project: str
    version: str
    python_version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Return the health status of the application."""
    return HealthResponse(
        status="ok", project="InsureVN", version="0.1.0", python_version=sys.version
    )
