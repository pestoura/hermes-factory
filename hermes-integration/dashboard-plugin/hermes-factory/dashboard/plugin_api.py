import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from hermes_factory.dashboard import FactoryDashboardProjection
from hermes_factory.traceability.registry import SemanticRegistry

router = APIRouter()


def _registry_path() -> Path:
    configured = os.environ.get("HERMES_FACTORY_REGISTRY_PATH")
    if configured is None or not configured.strip():
        raise HTTPException(
            status_code=503,
            detail="Hermes Factory registry is not configured",
        )
    return Path(configured)


@router.get("/snapshot")
async def snapshot(candidate: str | None = None) -> dict[str, object]:
    registry = SemanticRegistry(_registry_path())
    return FactoryDashboardProjection(registry).snapshot(candidate=candidate)
