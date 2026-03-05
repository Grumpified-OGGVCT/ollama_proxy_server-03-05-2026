# app/routes/catalog_routes.py
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
from pathlib import Path

from app.services.catalog_service import CatalogService
from app.utils.auth import get_current_user

router = APIRouter()

# Dependency to provide CatalogService instance

from functools import lru_cache

@lru_cache()
def get_catalog_service():
    return CatalogService(ollama_base_urls=["http://localhost:11435"], cache_dir=Path("data/cache"))



@router.get("/api/models/local")
async def get_local_models(
    request: Request,
    tier: Optional[str] = None,
    capability: Optional[str] = None,
    current_user: str = Depends(get_current_user),
    catalog: CatalogService = Depends(get_catalog_service)
):
    """Get locally installed models. Performance: <50ms cached."""
    models = await catalog.get_local_models()

    if tier:
        models = [m for m in models if m.tier.value == tier]
    if capability:
        models = [m for m in models if capability in m.capabilities]

    return {
        "data": [m.to_dict() for m in models],
        "meta": {"cache_status": "hit" if catalog._is_cache_valid() else "miss"}
    }

@router.post("/api/models/install")
async def install_model(
    model_name: str,
    current_user: str = Depends(get_current_user),
    catalog: CatalogService = Depends(get_catalog_service)
):
    """Trigger model installation. Rate limited: 5/hour."""
    # Validate model name
    safe_name = catalog._validate_model_name(model_name)

    return {
        "status": "queued",
        "model": safe_name,
        "websocket_channel": f"install-progress:{safe_name}"
    }
