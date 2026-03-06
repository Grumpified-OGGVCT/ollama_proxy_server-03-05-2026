# app/models/catalog.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class ModelTier(Enum):
    NANO = "nano"  # ≤3B params, <2GB VRAM
    FAST = "fast"  # ≤8B params, <6GB VRAM
    BALANCED = "balanced"  # ≤14B params, <10GB VRAM
    DEEP = "deep"  # >14B params, CPU offload


class ModelSource(Enum):
    OLLAMA_LOCAL = "ollama_local"
    OLLAMA_CLOUD = "ollama_cloud"
    VLLM = "vllm"
    OPENROUTER = "openrouter"
    # Legacy fallbacks
    LOCAL = "local"
    CLOUD = "cloud"


class ModelStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass(slots=True)
class PerformanceMetrics:
    first_token_ms: Optional[float] = None
    tokens_per_second: Optional[float] = None
    benchmark_score: Optional[float] = None
    timeout_rate: float = 0.0
    error_rate: float = 0.0
    last_benchmark_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "first_token_ms": self.first_token_ms,
            "tokens_per_second": self.tokens_per_second,
            "benchmark_score": self.benchmark_score,
            "timeout_rate": self.timeout_rate,
            "error_rate": self.error_rate,
            "last_benchmark_at": self.last_benchmark_at.isoformat() if self.last_benchmark_at else None,
        }


@dataclass(slots=True)
class LocalModel:
    id: str
    name: str
    tag: str
    tier: ModelTier
    source: ModelSource = ModelSource.LOCAL
    size_bytes: int = 0
    quantization: str = "unknown"
    parameter_size: str = "unknown"
    family: str = "unknown"
    context_length: int = 4096
    capabilities: List[str] = field(default_factory=list)
    hidden_size: Optional[int] = None
    num_layers: Optional[int] = None
    vocab_size: Optional[int] = None
    installed_at: datetime = field(default_factory=datetime.utcnow)
    last_used: datetime = field(default_factory=datetime.utcnow)
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    status: ModelStatus = ModelStatus.HEALTHY

    @property
    def size_gb(self) -> float:
        return self.size_bytes / (1024**3)

    @property
    def fits_hardware(self) -> bool:
        """Check if model + KV cache fits RTX 3060 12GB constraints (10GB max)."""
        if not self.hidden_size or not self.num_layers:
            return self.size_gb <= 7.0  # Conservative 3GB headroom

        context_length = min(self.context_length, 8192)
        kv_cache_bytes = 2 * self.num_layers * self.hidden_size * context_length * 2
        kv_cache_gb = kv_cache_bytes / (1024**3)
        total_required = self.size_gb + kv_cache_gb
        return total_required <= 10.0  # RTX 3060 12GB less 2GB system overhead

    @property
    def estimated_kv_cache_gb(self) -> float:
        """Calculate KV cache footprint for given context length."""
        target_context = 8192
        if not self.hidden_size or not self.num_layers:
            return 2.0
        bytes_required = 2 * self.num_layers * self.hidden_size * target_context * 2
        return bytes_required / (1024**3)

    @property
    def full_name(self) -> str:
        return f"{self.name}:{self.tag}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "tag": self.tag,
            "tier": self.tier.value,
            "source": self.source.value,
            "size_bytes": self.size_bytes,
            "size_gb": round(self.size_gb, 2),
            "quantization": self.quantization,
            "parameter_size": self.parameter_size,
            "family": self.family,
            "context_length": self.context_length,
            "capabilities": self.capabilities,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "vocab_size": self.vocab_size,
            "estimated_kv_cache_gb": round(self.estimated_kv_cache_gb, 2),
            "installed_at": self.installed_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "metrics": self.metrics.to_dict(),
            "status": self.status.value,
            "fits_hardware": self.fits_hardware,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LocalModel":
        installed_at = datetime.fromisoformat(data["installed_at"]) if isinstance(data["installed_at"], str) else data["installed_at"]
        last_used = datetime.fromisoformat(data["last_used"]) if isinstance(data["last_used"], str) else data["last_used"]

        metrics_data = data.get("metrics", {})
        metrics = PerformanceMetrics(
            first_token_ms=metrics_data.get("first_token_ms"),
            tokens_per_second=metrics_data.get("tokens_per_second"),
            benchmark_score=metrics_data.get("benchmark_score"),
            timeout_rate=metrics_data.get("timeout_rate", 0.0),
            error_rate=metrics_data.get("error_rate", 0.0),
            last_benchmark_at=datetime.fromisoformat(metrics_data["last_benchmark_at"]) if metrics_data.get("last_benchmark_at") else None,
        )

        return cls(
            id=data["id"],
            name=data["name"],
            tag=data["tag"],
            tier=ModelTier(data["tier"]),
            source=ModelSource(data.get("source", "local")),
            size_bytes=data["size_bytes"],
            quantization=data["quantization"],
            parameter_size=data["parameter_size"],
            family=data["family"],
            context_length=data["context_length"],
            capabilities=data.get("capabilities", []),
            hidden_size=data.get("hidden_size"),
            num_layers=data.get("num_layers"),
            vocab_size=data.get("vocab_size"),
            installed_at=installed_at,
            last_used=last_used,
            metrics=metrics,
            status=ModelStatus(data.get("status", "healthy")),
        )


@dataclass(slots=True)
class CloudModel:
    id: str
    name: str
    provider: str
    model_card_name: str
    tier: ModelTier
    source: ModelSource = ModelSource.CLOUD
    context_length: int = 128000
    capabilities: List[str] = field(default_factory=list)
    cost_per_million_tokens: float = 0.0
    quota_risk: float = 0.0
    requires_opt_in: bool = False
    is_default_excluded: bool = False
    latency_p50_ms: Optional[float] = None
    quality_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "model_card_name": self.model_card_name,
            "tier": self.tier.value,
            "source": self.source.value,
            "context_length": self.context_length,
            "capabilities": self.capabilities,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "vocab_size": self.vocab_size,
            "estimated_kv_cache_gb": round(self.estimated_kv_cache_gb, 2),
            "cost_per_million_tokens": self.cost_per_million_tokens,
            "quota_risk": self.quota_risk,
            "requires_opt_in": self.requires_opt_in,
            "is_default_excluded": self.is_default_excluded,
            "latency_p50_ms": self.latency_p50_ms,
            "quality_score": self.quality_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CloudModel":
        return cls(
            id=data["id"],
            name=data["name"],
            provider=data["provider"],
            model_card_name=data["model_card_name"],
            tier=ModelTier(data["tier"]),
            source=ModelSource(data.get("source", "cloud")),
            context_length=data.get("context_length", 128000),
            capabilities=data.get("capabilities", []),
            hidden_size=data.get("hidden_size"),
            num_layers=data.get("num_layers"),
            vocab_size=data.get("vocab_size"),
            cost_per_million_tokens=data.get("cost_per_million_tokens", 0.0),
            quota_risk=data.get("quota_risk", 0.0),
            requires_opt_in=data.get("requires_opt_in", False),
            is_default_excluded=data.get("is_default_excluded", False),
            latency_p50_ms=data.get("latency_p50_ms"),
            quality_score=data.get("quality_score"),
        )


@dataclass(slots=True)
class CatalogState:
    version: str = "2026.3"
    local_instance: str = "http://localhost:11435"
    local_models: Dict[str, LocalModel] = field(default_factory=dict)
    cloud_models: Dict[str, CloudModel] = field(default_factory=dict)
    last_local_sync: Optional[datetime] = None
    last_cloud_sync: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "local_instance": self.local_instance,
            "local_models": {k: v.to_dict() for k, v in self.local_models.items()},
            "cloud_models": {k: v.to_dict() for k, v in self.cloud_models.items()},
            "last_local_sync": self.last_local_sync.isoformat() if self.last_local_sync else None,
            "last_cloud_sync": self.last_cloud_sync.isoformat() if self.last_cloud_sync else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CatalogState":
        local_models = {k: LocalModel.from_dict(v) for k, v in data.get("local_models", {}).items()}
        cloud_models = {k: CloudModel.from_dict(v) for k, v in data.get("cloud_models", {}).items()}

        return cls(
            version=data.get("version", "2026.3"),
            local_instance=data.get("local_instance", "http://localhost:11435"),
            local_models=local_models,
            cloud_models=cloud_models,
            last_local_sync=datetime.fromisoformat(data["last_local_sync"]) if data.get("last_local_sync") else None,
            last_cloud_sync=datetime.fromisoformat(data["last_cloud_sync"]) if data.get("last_cloud_sync") else None,
        )
