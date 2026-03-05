# tests/test_catalog_service.py
import pytest
from pathlib import Path
from app.services.catalog_service import CatalogService

@pytest.fixture
def catalog():
    # Provide a simple catalog fixture.
    return CatalogService(ollama_base_urls=[], cache_dir=Path("data/test_cache"))

def test_validate_model_name_security(catalog):
    """Block injection attempts."""
    malicious = ["model; rm -rf /", "../etc/passwd", "$(whoami)"]
    for name in malicious:
        with pytest.raises(ValueError):
            catalog._validate_model_name(name)

def test_cache_performance(catalog):
    """O(1) lookup performance."""
    import time
    from app.models.catalog import LocalModel, ModelTier

    # Pre-populate cache for the test
    catalog._state.local_models["local:test"] = LocalModel(
        id="local:test",
        name="test",
        tag="latest",
        tier=ModelTier.BALANCED,
        size_bytes=1000
    )

    start = time.perf_counter()
    for _ in range(1000):
        catalog.get_model_by_id("local:test")
    elapsed = (time.perf_counter() - start) * 1000
    assert elapsed < 100  # 1000 lookups in <100ms
