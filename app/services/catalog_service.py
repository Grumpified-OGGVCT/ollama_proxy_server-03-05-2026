# app/services/catalog_service.py
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiohttp
import aiofiles

from app.models.catalog import LocalModel, CloudModel, CatalogState, ModelTier, ModelStatus, PerformanceMetrics


class CatalogService:
    """
    Dual catalog management with O(1) cached lookups.

    Performance: <50ms cached retrieval, <5s cache miss for 5 servers.
    Security: All model names validated against injection patterns.
    """

    CACHE_TTL_SECONDS = 300  # 5 minutes for local
    MODEL_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]*(/[a-z0-9][a-z0-9_.-]*)?(:[a-z0-9_.-]+)?$")
    MAX_MODEL_NAME_LENGTH = 128

    def __init__(self, ollama_base_urls: List[str], cache_dir: Path, hardware_profile: Optional[Any] = None):
        self.ollama_urls = ollama_base_urls
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._state = CatalogState(local_instance=ollama_base_urls[0] if ollama_base_urls else "http://localhost:11435")
        self._state_file = cache_dir / "catalog_state.json"
        self._load_from_disk()

    def _validate_model_name(self, model_name: str) -> str:
        """
        Security: Prevent command injection, path traversal, shell expansion.
        """
        if not model_name:
            raise ValueError("Model name cannot be empty")

        if len(model_name) > self.MAX_MODEL_NAME_LENGTH:
            raise ValueError(f"Model name exceeds max length of {self.MAX_MODEL_NAME_LENGTH}")

        if not self.MODEL_NAME_PATTERN.match(model_name):
            raise ValueError(f"Invalid model name format: {model_name}")

        if ".." in model_name or model_name.startswith("/"):
            raise ValueError("Path traversal not allowed")

        return model_name

    async def get_local_models(self, use_cache: bool = True) -> List[LocalModel]:
        """
        Performance: O(1) cached, O(n) parallel fetch on miss.
        """
        if use_cache and self._is_cache_valid():
            return list(self._state.local_models.values())

        tasks = [self._fetch_from_server(url) for url in self.ollama_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        merged: Dict[str, LocalModel] = {}
        for result in results:
            if isinstance(result, Exception):
                continue
            for model in result:
                if model.id not in merged or model.installed_at > merged[model.id].installed_at:
                    merged[model.id] = model

        self._state.local_models = merged
        self._state.last_local_sync = datetime.utcnow()
        await self._persist_to_disk()

        return list(merged.values())

    async def _fetch_from_server(self, base_url: str) -> List[LocalModel]:
        """Fetch models from single Ollama server with concurrency limit."""
        models: List[LocalModel] = []
        timeout = aiohttp.ClientTimeout(total=10, connect=5)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(f"{base_url}/api/tags") as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()

                # Concurrency limit: max 5 concurrent detail fetches
                semaphore = asyncio.Semaphore(5)

                async def fetch_model_details(model_data: Dict[str, Any]) -> Optional[LocalModel]:
                    async with semaphore:
                        return await self._parse_model(model_data, base_url, session)

                detail_tasks = [fetch_model_details(m) for m in data.get("models", [])]
                detail_results = await asyncio.gather(*detail_tasks, return_exceptions=True)

                for result in detail_results:
                    if isinstance(result, LocalModel):
                        models.append(result)

            except aiohttp.ClientError:
                return []

        return models

    async def _parse_model(self, model_data: Dict[str, Any], base_url: str, session: aiohttp.ClientSession) -> Optional[LocalModel]:
        """Parse single model from Ollama API response."""
        try:
            model_name = self._validate_model_name(model_data.get("name", ""))

            detail_data = {}
            try:
                async with session.post(f"{base_url}/api/show", json={"name": model_name}, timeout=aiohttp.ClientTimeout(total=3)) as detail_resp:
                    if detail_resp.status == 200:
                        detail_data = await detail_resp.json()
            except aiohttp.ClientError:
                pass

            details = detail_data.get("details", {})
            param_size = details.get("parameter_size", "unknown")

            model_info = detail_data.get("model_info", {})
            return LocalModel(
                id=f"local:{model_name}",
                name=model_name.split(":")[0],
                tag=model_name.split(":")[-1] if ":" in model_name else "latest",
                tier=self._determine_tier(param_size),
                size_bytes=model_data.get("size", 0),
                quantization=details.get("quantization_level", "unknown"),
                parameter_size=param_size,
                family=details.get("family", "unknown"),
                context_length=self._extract_context_length(detail_data),
                capabilities=self._extract_capabilities(detail_data),
                hidden_size=model_info.get("hidden_size") if "hidden_size" in model_info else model_info.get("llama.embedding_length"),
                num_layers=model_info.get("num_layers") if "num_layers" in model_info else model_info.get("llama.block_count"),
                vocab_size=model_info.get("vocab_size"),
                installed_at=datetime.fromisoformat(model_data["modified_at"].replace("Z", "+00:00")) if "modified_at" in model_data else datetime.utcnow(),
                status=ModelStatus.HEALTHY,
            )

        except (ValueError, KeyError, TypeError):
            return None

    def _determine_tier(self, param_size: str) -> ModelTier:
        """Map parameter size to tier for RTX 3060 optimization."""
        try:
            if "b" in param_size.lower():
                size = float(param_size.lower().replace("b", "").replace("m", ""))
                if size <= 3:
                    return ModelTier.NANO
                elif size <= 8:
                    return ModelTier.FAST
                elif size <= 14:
                    return ModelTier.BALANCED
                else:
                    return ModelTier.DEEP
        except (ValueError, AttributeError):
            pass
        return ModelTier.BALANCED

    def _extract_context_length(self, detail: Dict[str, Any]) -> int:
        """Extract context length from model details."""
        # Priority 1: Explicit model_info.context_length (Ollama 0.4.0+)
        model_info = detail.get("model_info", {})
        if "context_length" in model_info:
            return int(model_info["context_length"])

        # Priority 2: Modelfile PARAMETER num_ctx
        modelfile = detail.get("modelfile", "")
        for line in modelfile.split("\n"):
            if "PARAMETER" in line and "num_ctx" in line:
                try:
                    return int(line.split()[-1])
                except (ValueError, IndexError):
                    pass

        # Priority 3: Updated family defaults for 2026
        family = detail.get("details", {}).get("family", "").lower()
        defaults = {
            "llama": 128000,  # Llama 3/4 standard
            "mistral": 128000,  # Mistral Large 3
            "qwen": 128000,  # Qwen 2.5/3
            "gemma": 8192,  # Gemma 2/3
            "phi": 128000,  # Phi-4
            "deepseek": 128000,  # DeepSeek V3/R1
        }
        return defaults.get(family, 4096)  # Conservative fallback

    def _extract_capabilities(self, detail: Dict[str, Any]) -> List[str]:
        """Extract capabilities from model metadata."""
        caps = []
        family = detail.get("details", {}).get("family", "").lower()
        name = detail.get("name", "").lower()
        model_id = detail.get("id", "").lower() if "id" in detail else ""

        if "coder" in name or "code" in family:
            caps.append("coding")
        if "vision" in name or "vl" in name:
            caps.append("vision")
        if "tool" in name:
            caps.append("tool_use")

        reasoning_indicators = ["r1", "reasoning", "thought", "cot", "deepseek-r1", "qwen3-distill", "llama4-r", "kimi-k2-thinking"]
        if any(ind in name or ind in model_id for ind in reasoning_indicators):
            caps.append("reasoning")

        tags = detail.get("tags", [])
        if any("thinking" in str(tag).lower() or "reasoning" in str(tag).lower() for tag in tags):
            if "reasoning" not in caps:
                caps.append("reasoning")

        return caps

    def _is_cache_valid(self) -> bool:
        if not self._state.last_local_sync:
            return False
        age = (datetime.utcnow() - self._state.last_local_sync).total_seconds()
        return age < self.CACHE_TTL_SECONDS

    async def _persist_to_disk(self) -> None:
        """Atomic write to disk for crash recovery."""
        temp_file = self._state_file.with_suffix(".tmp")

        try:
            async with aiofiles.open(temp_file, "w") as f:
                await f.write(json.dumps(self._state.to_dict(), default=str, indent=2))

            temp_file.replace(self._state_file)

        except Exception:
            if temp_file.exists():
                temp_file.unlink()

    def _load_from_disk(self) -> None:
        """Load persisted state on startup."""
        if not self._state_file.exists():
            return

        try:
            with open(self._state_file, "r") as f:
                data = json.load(f)

            self._state = CatalogState.from_dict(data)

        except (json.JSONDecodeError, KeyError, ValueError):
            self._state = CatalogState(local_instance=self.ollama_urls[0] if self.ollama_urls else "http://localhost:11435")

    def get_model_by_id(self, model_id: str) -> Optional[LocalModel]:
        """O(1) lookup by model ID."""
        return self._state.local_models.get(model_id)

    def get_models_by_tier(self, tier: ModelTier) -> List[LocalModel]:
        """Filter models by tier."""
        return [m for m in self._state.local_models.values() if m.tier == tier]

    def get_models_by_capability(self, capability: str) -> List[LocalModel]:
        """Filter models by capability."""
        return [m for m in self._state.local_models.values() if capability in m.capabilities]

    async def get_cloud_models(self, use_cache: bool = True) -> List[CloudModel]:
        """Performance: O(1) cached, O(n) fetch on miss."""
        if use_cache and self._state.last_cloud_sync:
            age = (datetime.utcnow() - self._state.last_cloud_sync).total_seconds()
            if age < self.CACHE_TTL_SECONDS:
                return list(self._state.cloud_models.values())

        # Parallel fetch for enabled providers
        tasks = []
        # In a real impl, you'd check settings.enable_openrouter here
        tasks.append(self._fetch_openrouter_models())
        tasks.append(self._fetch_ollama_cloud_models())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        merged: Dict[str, CloudModel] = {}
        for result in results:
            if isinstance(result, Exception):
                continue
            for model in result:
                merged[model.id] = model

        self._state.cloud_models = merged
        self._state.last_cloud_sync = datetime.utcnow()
        await self._persist_to_disk()

        return list(merged.values())

    async def _fetch_openrouter_models(self) -> List[CloudModel]:
        models: List[CloudModel] = []
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get("https://openrouter.ai/api/v1/models") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for m in data.get("data", []):
                            price = m.get("pricing", {})
                            prompt_cost = float(price.get("prompt", 0) or 0)
                            completion_cost = float(price.get("completion", 0) or 0)
                            cost_pm = (prompt_cost + completion_cost) * 1000000

                            models.append(
                                CloudModel(
                                    id=f"openrouter:{m.get('id')}",
                                    name=m.get("id"),
                                    provider="openrouter",
                                    model_card_name=m.get("name", ""),
                                    tier=ModelTier.DEEP if "70b" in m.get("id", "").lower() else ModelTier.BALANCED,
                                    context_length=int(m.get("context_length", 8192)),
                                    cost_per_million_tokens=cost_pm,
                                    is_default_excluded=False,
                                )
                            )
            except Exception:
                pass
        return models

    async def _fetch_ollama_cloud_models(self) -> List[CloudModel]:
        models: List[CloudModel] = []
        # Mocking Ollama Cloud fetch as the endpoint structure isn't fully standardized
        # In production this would hit https://api.ollama.cloud/v1/models
        models.append(
            CloudModel(
                id="ollama-cloud:llama3.3",
                name="llama3.3",
                provider="ollama-cloud",
                model_card_name="Llama 3.3 Cloud",
                tier=ModelTier.DEEP,
                context_length=128000,
                cost_per_million_tokens=0.5,
            )
        )
        return models

    async def update_model_metrics(self, model_id: str, metrics: PerformanceMetrics) -> None:
        """Update performance metrics for a model."""
        if model_id in self._state.local_models:
            old_context = self._state.local_models[model_id].context_length
            self._state.local_models[model_id].metrics = metrics

            # Check for context length mismatch indicating Modelfile update
            if getattr(metrics, "context_length", None) and metrics.context_length != old_context:
                self._state.local_models[model_id].context_length = metrics.context_length
                await self._persist_to_disk()
                # Assuming broadcast_invalidation logic exists or will just log
                # await self._broadcast_invalidation(model_id, "context_length_changed")
