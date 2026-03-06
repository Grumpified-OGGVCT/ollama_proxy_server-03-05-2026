# Automated Model Matrix — Exhaustive Technical Reference

> **Version:** 2026.3 · **Applies to:** Ollama Proxy Fortress v9+

This document is the single authoritative reference for every component of the automated model matrix: what it is, how every layer of code interacts, every field, every threshold, every timing value, every security guardrail, and the full data lifecycle from raw server API response through to an API consumer receiving a streamed reply.

---

## Table of Contents

1. [What is the Automated Model Matrix?](#1-what-is-the-automated-model-matrix)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Data Layer — Every Type Explained](#3-data-layer--every-type-explained)
   - 3.1 [ModelTier](#31-modeltier)
   - 3.2 [ModelSource](#32-modelsource)
   - 3.3 [ModelStatus](#33-modelstatus)
   - 3.4 [PerformanceMetrics](#34-performancemetrics)
   - 3.5 [LocalModel](#35-localmodel)
   - 3.6 [CloudModel](#36-cloudmodel)
   - 3.7 [CatalogState](#37-catalogstate)
   - 3.8 [ModelMetadata (Database)](#38-modelmetadata-database)
   - 3.9 [OllamaServer.available_models (Database)](#39-ollamaserveravailable_models-database)
4. [CatalogService — The In-Memory Catalog Engine](#4-catalogservice--the-in-memory-catalog-engine)
   - 4.1 [Initialization and Disk Recovery](#41-initialization-and-disk-recovery)
   - 4.2 [Security: Model Name Validation](#42-security-model-name-validation)
   - 4.3 [Fetching Local Models — Parallel with Semaphore](#43-fetching-local-models--parallel-with-semaphore)
   - 4.4 [Parsing Individual Models](#44-parsing-individual-models)
   - 4.5 [Context Length Extraction](#45-context-length-extraction)
   - 4.6 [Capability Extraction](#46-capability-extraction)
   - 4.7 [Cache TTL and Validity](#47-cache-ttl-and-validity)
   - 4.8 [Atomic Disk Persistence](#48-atomic-disk-persistence)
   - 4.9 [O(1) Lookup Methods](#49-o1-lookup-methods)
5. [Database-Level Ingestion Pipeline — fetch_and_update_models](#5-database-level-ingestion-pipeline--fetch_and_update_models)
   - 5.1 [Ollama Protocol Path](#51-ollama-protocol-path)
   - 5.2 [vLLM (OpenAI-Compatible) Protocol Path](#52-vllm-openai-compatible-protocol-path)
   - 5.3 [Security Sanitization at Ingestion](#53-security-sanitization-at-ingestion)
   - 5.4 [Hard Caps and DoS Prevention](#54-hard-caps-and-dos-prevention)
   - 5.5 [Commit and Error Recording](#55-commit-and-error-recording)
6. [Automated Refresh Background Task](#6-automated-refresh-background-task)
   - 6.1 [periodic_model_refresh Loop](#61-periodic_model_refresh-loop)
   - 6.2 [refresh_all_server_models Orchestrator](#62-refresh_all_server_models-orchestrator)
   - 6.3 [Startup Initial Refresh](#63-startup-initial-refresh)
   - 6.4 [Graceful Shutdown and Cancellation](#64-graceful-shutdown-and-cancellation)
   - 6.5 [Live Interval Updates](#65-live-interval-updates)
7. [Auto-Routing Intelligence — _select_auto_model](#7-auto-routing-intelligence--_select_auto_model)
   - 7.1 [Input Signal Extraction](#71-input-signal-extraction)
   - 7.2 [Image-Support Filter](#72-image-support-filter)
   - 7.3 [Code-Keyword Filter](#73-code-keyword-filter)
   - 7.4 [Fast-Model Option Filter](#74-fast-model-option-filter)
   - 7.5 [Priority Ordering and Final Selection](#75-priority-ordering-and-final-selection)
   - 7.6 [Fallback Strategy](#76-fallback-strategy)
8. [Smart Model Routing — get_servers_with_model](#8-smart-model-routing--get_servers_with_model)
   - 8.1 [Exact Match](#81-exact-match)
   - 8.2 [Prefix Match](#82-prefix-match)
   - 8.3 [vLLM Substring Match](#83-vllm-substring-match)
   - 8.4 [Fallback to Round-Robin](#84-fallback-to-round-robin)
9. [Federated Model View — GET /api/tags](#9-federated-model-view--get-apitags)
   - 9.1 [Deduplication by Model Name](#91-deduplication-by-model-name)
   - 9.2 [The Synthetic "auto" Model Entry](#92-the-synthetic-auto-model-entry)
10. [Retry Engine — retry_with_backoff](#10-retry-engine--retry_with_backoff)
    - 10.1 [RetryConfig Fields and Defaults](#101-retryconfig-fields-and-defaults)
    - 10.2 [Exponential Backoff Formula](#102-exponential-backoff-formula)
    - 10.3 [Total Timeout Budget Enforcement](#103-total-timeout-budget-enforcement)
    - 10.4 [RetryResult Structure](#104-retryresult-structure)
11. [Security Hardening](#11-security-hardening)
    - 11.1 [SSRF Prevention — _is_safe_url](#111-ssrf-prevention--_is_safe_url)
    - 11.2 [Injection Prevention at Every Layer](#112-injection-prevention-at-every-layer)
    - 11.3 [Model List Size Caps](#113-model-list-size-caps)
    - 11.4 [Error Message Truncation](#114-error-message-truncation)
12. [Configuration Reference](#12-configuration-reference)
13. [REST API Catalog Endpoints](#13-rest-api-catalog-endpoints)
14. [End-to-End Data Flow Diagrams](#14-end-to-end-data-flow-diagrams)
    - 14.1 [Startup Refresh Flow](#141-startup-refresh-flow)
    - 14.2 [Periodic Background Refresh Flow](#142-periodic-background-refresh-flow)
    - 14.3 [API Request Auto-Routing Flow](#143-api-request-auto-routing-flow)
    - 14.4 [Smart Model Routing Decision Tree](#144-smart-model-routing-decision-tree)
15. [Glossary](#15-glossary)

---

## 1. What is the Automated Model Matrix?

The **Automated Model Matrix** is the subsystem in Ollama Proxy Fortress that:

1. **Discovers** which AI models are installed on every configured backend server (Ollama and/or vLLM), both at startup and on a configurable repeating schedule.
2. **Classifies** each discovered model by tier (hardware requirement class), capability (vision, coding, tool use), and quality metadata maintained by the administrator.
3. **Persists** the discovered state in both a SQLite JSON column (per-server) and an on-disk cache file (for the in-memory CatalogService layer), so that a cold restart never leaves the proxy blind to existing models.
4. **Exposes** a unified, federated view of all models from all backends to API consumers, including a synthetic `auto` model entry that acts as a "smart router."
5. **Routes** each incoming request to the single most appropriate server — or, in `auto` mode, also selects the most appropriate model — based on the content of the request, pre-configured metadata priority, and live server availability.
6. **Retries** failed backend calls with configurable exponential backoff, transparently to the API consumer.

In short: from the API consumer's perspective, there is one pool of models, one endpoint, and always a best-effort intelligent routing layer that is maintained with zero manual intervention.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       FastAPI Application                           │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                  Lifespan (startup/shutdown)                 │  │
│   │  ┌──────────────────────────────────────────────────────┐   │  │
│   │  │  1. init_db / run_all_migrations                     │   │  │
│   │  │  2. Load AppSettings from DB                         │   │  │
│   │  │  3. Create admin user if absent                       │   │  │
│   │  │  4. Connect to Redis (rate limiting)                  │   │  │
│   │  │  5. ──► INITIAL MODEL REFRESH ◄──                    │   │  │
│   │  │  6. Start background task: periodic_model_refresh     │   │  │
│   │  └──────────────────────────────────────────────────────┘   │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│   ┌─────────────────────┐   ┌───────────────────────────────────┐  │
│   │   Proxy Router      │   │  Background Task                  │  │
│   │  /api/{path}        │   │  periodic_model_refresh           │  │
│   │   ↓                 │   │   ↓ every model_update_interval   │  │
│   │  Auto-Routing?      │   │  refresh_all_server_models        │  │
│   │   ↓                 │   │   ↓                               │  │
│   │  Smart Routing      │   │  fetch_and_update_models (x N)    │  │
│   │   ↓                 │   │   ↓                               │  │
│   │  Retry Engine       │   │  OllamaServer.available_models    │  │
│   │   ↓                 │   │  (JSON in SQLite)                 │  │
│   │  Backend Server     │   └───────────────────────────────────┘  │
│   └─────────────────────┘                                          │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │              CatalogService (in-memory)                     │  │
│   │  CatalogState ──► local_models (dict) + cloud_models (dict) │  │
│   │  Cache file: data/cache/catalog_state.json                  │  │
│   └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
        │                                   │
        ▼                                   ▼
  Ollama Servers                       vLLM Servers
  /api/tags   (GET)                    /v1/models  (GET)
  /api/show   (POST)                   (no individual detail endpoint)
```

There are **two parallel but complementary** model catalogs:

| Catalog | Location | Updated by | Consumed by |
|---------|----------|------------|-------------|
| **OllamaServer.available_models** | SQLite `ollama_servers` table, JSON column | `fetch_and_update_models` | Proxy routing, smart routing, `/api/tags`, admin UI |
| **CatalogService._state** | In-memory + `data/cache/catalog_state.json` | `CatalogService.get_local_models()` | `/api/models/local`, tier/capability filters |

Both are kept in sync through the same underlying Ollama `/api/tags` + `/api/show` calls, but serve different consumers with different performance characteristics.

---

## 3. Data Layer — Every Type Explained

### 3.1 ModelTier

**File:** `app/models/catalog.py`

```python
class ModelTier(Enum):
    NANO     = "nano"       # ≤3B params  → <2 GB VRAM
    FAST     = "fast"       # ≤8B params  → <6 GB VRAM
    BALANCED = "balanced"   # ≤14B params → <10 GB VRAM
    DEEP     = "deep"       # >14B params → CPU offload required
```

The tier is determined by `CatalogService._determine_tier(param_size: str)` at ingestion time:

```
param_size string  →  extracted float  →  tier decision
"3.8B"             →  3.8              →  FAST      (3 < 3.8 ≤ 8)
"7B"               →  7.0              →  FAST      (3 < 7 ≤ 8)
"13B"              →  13.0             →  BALANCED  (8 < 13 ≤ 14)
"70B"              →  70.0             →  DEEP      (70 > 14)
"1.5B"             →  1.5              →  NANO      (1.5 ≤ 3)
"unknown"          →  parse error      →  BALANCED  (safe default)
```

The thresholds are explicitly tuned for an **RTX 3060 12 GB** reference card, but the `LocalModel.fits_hardware` property (described below) applies the final 10 GB ceiling check regardless of tier.

### 3.2 ModelSource

```python
class ModelSource(Enum):
    LOCAL = "local"    # Installed on a local Ollama instance
    CLOUD = "cloud"    # A cloud-hosted model descriptor
```

`LocalModel` always has `source=LOCAL`. `CloudModel` always has `source=CLOUD`. The field is serialized to the API response JSON as the string value.

### 3.3 ModelStatus

```python
class ModelStatus(Enum):
    HEALTHY  = "healthy"   # Fully operational
    WARNING  = "warning"   # Experiencing elevated errors
    DEGRADED = "degraded"  # Partially operational
    OFFLINE  = "offline"   # Unreachable
```

During ingestion, every successfully parsed `LocalModel` is assigned `ModelStatus.HEALTHY`. The proxy does not yet automatically degrade status based on error rate tracking (the `PerformanceMetrics.error_rate` field collects the data that would drive this in a future release). Status changes can be applied externally via `CatalogService.update_model_metrics()`.

### 3.4 PerformanceMetrics

**File:** `app/models/catalog.py`

```python
@dataclass(slots=True)
class PerformanceMetrics:
    first_token_ms: Optional[float] = None       # Time-to-first-token in milliseconds
    tokens_per_second: Optional[float] = None    # Sustained generation throughput
    benchmark_score: Optional[float] = None      # Composite benchmark score (0-100)
    timeout_rate: float = 0.0                    # Fraction of requests that timed out
    error_rate: float = 0.0                      # Fraction of requests that errored
    last_benchmark_at: Optional[datetime] = None # When the last benchmark was run
```

All fields default to `None` / `0.0` at discovery time. They are populated via `CatalogService.update_model_metrics(model_id, metrics)` when benchmark data is collected through the Embedding Playground or Chat Playground.

The `slots=True` on the dataclass eliminates the per-instance `__dict__`, reducing memory overhead when the catalog holds hundreds of models.

**Serialization:**

```python
def to_dict(self) -> Dict[str, Any]:
    return {
        "first_token_ms":   self.first_token_ms,
        "tokens_per_second": self.tokens_per_second,
        "benchmark_score":  self.benchmark_score,
        "timeout_rate":     self.timeout_rate,
        "error_rate":       self.error_rate,
        "last_benchmark_at": self.last_benchmark_at.isoformat() if self.last_benchmark_at else None
    }
```

### 3.5 LocalModel

**File:** `app/models/catalog.py`

The central data structure representing a model physically installed on one of the configured Ollama backends.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `id` | `str` | Computed | `"local:{model_name}"` — globally unique key within the catalog |
| `name` | `str` | `model_data["name"].split(":")[0]` | Base name without tag |
| `tag` | `str` | Split from full name | `"latest"` if no colon |
| `tier` | `ModelTier` | `_determine_tier(param_size)` | Hardware class |
| `source` | `ModelSource` | Hardcoded | Always `LOCAL` |
| `size_bytes` | `int` | `model_data["size"]` | Raw file size from `/api/tags` |
| `quantization` | `str` | `details["quantization_level"]` | e.g. `"Q4_K_M"` |
| `parameter_size` | `str` | `details["parameter_size"]` | e.g. `"7B"` |
| `family` | `str` | `details["family"]` | e.g. `"llama"` |
| `context_length` | `int` | `_extract_context_length()` | From modelfile or family default |
| `capabilities` | `List[str]` | `_extract_capabilities()` | `["coding"]`, `["vision"]`, etc. |
| `installed_at` | `datetime` | `model_data["modified_at"]` | UTC; last modification time |
| `last_used` | `datetime` | `datetime.utcnow()` | Populated at construction |
| `metrics` | `PerformanceMetrics` | Default | Populated later by benchmarks |
| `status` | `ModelStatus` | Hardcoded at parse | `HEALTHY` on successful discovery |

**Computed properties:**

```python
@property
def size_gb(self) -> float:
    return self.size_bytes / (1024 ** 3)

@property
def fits_hardware(self) -> bool:
    """True if model ≤10 GB on disk (RTX 3060 12GB safe zone)."""
    return self.size_gb <= 10.0

@property
def full_name(self) -> str:
    return f"{self.name}:{self.tag}"
```

**Deduplication logic (across multiple servers):**

When `get_local_models()` merges results from N servers, the rule is:

```
If model_id exists in merged already:
    Keep the entry with the more recent installed_at timestamp.
```

This ensures that the canonical record in the catalog reflects the most recently updated copy of a model across the fleet.

### 3.6 CloudModel

**File:** `app/models/catalog.py`

Represents a cloud-hosted model descriptor (not yet auto-populated; reserved for future cloud provider integrations).

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `id` | `str` | — | e.g. `"cloud:openai:gpt-4o"` |
| `name` | `str` | — | Human-readable name |
| `provider` | `str` | — | e.g. `"openai"`, `"anthropic"` |
| `model_card_name` | `str` | — | Official model card identifier |
| `tier` | `ModelTier` | — | Performance classification |
| `source` | `ModelSource` | `CLOUD` | Always cloud |
| `context_length` | `int` | `128000` | Default assumes large context |
| `capabilities` | `List[str]` | `[]` | e.g. `["vision", "tool_use"]` |
| `cost_per_million_tokens` | `float` | `0.0` | Billing cost |
| `quota_risk` | `float` | `0.0` | 0.0–1.0 risk of hitting quota |
| `requires_opt_in` | `bool` | `False` | Access-gated models |
| `is_default_excluded` | `bool` | `False` | Hidden from default selection |
| `latency_p50_ms` | `Optional[float]` | `None` | Median latency in ms |
| `quality_score` | `Optional[float]` | `None` | Benchmark quality score |

### 3.7 CatalogState

**File:** `app/models/catalog.py`

The top-level container that is both held in RAM by `CatalogService` and serialized to disk for crash recovery.

```python
@dataclass(slots=True)
class CatalogState:
    version: str = "2026.3"
    local_instance: str = "http://localhost:11435"
    local_models: Dict[str, LocalModel] = field(default_factory=dict)
    cloud_models: Dict[str, CloudModel] = field(default_factory=dict)
    last_local_sync: Optional[datetime] = None
    last_cloud_sync: Optional[datetime] = None
```

| Field | Description |
|-------|-------------|
| `version` | Schema version string for forward-compatible deserialization |
| `local_instance` | The primary Ollama URL (first element of `ollama_base_urls`) |
| `local_models` | Dict keyed by `LocalModel.id` — the hot cache for O(1) lookups |
| `cloud_models` | Dict keyed by `CloudModel.id` — populated by future cloud integrations |
| `last_local_sync` | UTC timestamp of the last successful local model fetch |
| `last_cloud_sync` | UTC timestamp of the last successful cloud model fetch |

`CatalogState.to_dict()` / `CatalogState.from_dict()` provide full round-trip serialization with ISO 8601 datetime strings and graceful defaults on partial data.

### 3.8 ModelMetadata (Database)

**File:** `app/database/models.py`

The administrator-curated metadata layer. While `LocalModel` is auto-discovered, `ModelMetadata` is a SQLite record that an operator populates (or that is auto-created with safe defaults) to guide the auto-routing engine.

```python
class ModelMetadata(Base):
    __tablename__ = "model_metadata"
    id            = Column(Integer, primary_key=True, index=True)
    model_name    = Column(String, unique=True, index=True, nullable=False)
    description   = Column(String, nullable=True)
    supports_images = Column(Boolean, default=False, nullable=False)
    is_code_model   = Column(Boolean, default=False, nullable=False)
    is_chat_model   = Column(Boolean, default=True,  nullable=False)
    is_fast_model   = Column(Boolean, default=False, nullable=False)
    priority        = Column(Integer, default=10,    nullable=False)
```

| Field | Purpose in auto-routing |
|-------|-------------------------|
| `model_name` | The exact name as returned by the backend (e.g. `"llava:13b"`) |
| `supports_images` | Enables the image-support filter in `_select_auto_model` |
| `is_code_model` | Enables the code-keyword filter |
| `is_chat_model` | General flag; checked by the Chat Playground model list |
| `is_fast_model` | Enables the `fast_model` option filter |
| `priority` | Lower integer = higher priority; controls tie-breaking; default `10` |

**Auto-creation:** When a model is discovered during routing that has no existing `ModelMetadata` row, `model_metadata_crud.get_or_create_metadata()` inserts a safe default row. The only heuristic applied at creation time is:

```python
supports_images_default = "llava" in model_name or "bakllava" in model_name
```

All other flags default to `False` / `True` (chat only, not fast, not code). The administrator configures the rest through the admin UI Models Manager page.

**Sort order:** `get_all_metadata()` returns records ordered by `(priority ASC, model_name ASC)`, ensuring that deterministic priority-based selection applies to the auto-router.

### 3.9 OllamaServer.available_models (Database)

**File:** `app/database/models.py`

```python
class OllamaServer(Base):
    __tablename__ = "ollama_servers"
    id                  = Column(Integer, primary_key=True, index=True)
    name                = Column(String, nullable=False)
    url                 = Column(String, unique=True, nullable=False)
    server_type         = Column(String, nullable=False, default="ollama")
    encrypted_api_key   = Column(String, nullable=True)
    is_active           = Column(Boolean, default=True)
    available_models    = Column(JSON, nullable=True)       ← model matrix store
    models_last_updated = Column(DateTime, nullable=True)
    last_error          = Column(String, nullable=True)
    created_at          = Column(DateTime, default=datetime.datetime.utcnow)
```

`available_models` is a **JSON array** stored directly in SQLite. Each element conforms to the following sanitized structure (produced by `fetch_and_update_models`):

```json
{
  "name":        "llama3:8b",
  "size":        4920000000,
  "modified_at": "2025-11-01T12:00:00+00:00",
  "digest":      "sha256abcdef1234",
  "details": {
    "parent_model":        "",
    "format":              "gguf",
    "family":              "llama",
    "families":            ["llama"],
    "parameter_size":      "8B",
    "quantization_level":  "Q4_K_M"
  }
}
```

For vLLM servers, `size` is always `0` (the vLLM API does not expose file sizes), and `digest` is set to the model ID as a stand-in.

---

## 4. CatalogService — The In-Memory Catalog Engine

**File:** `app/services/catalog_service.py`

`CatalogService` provides the high-performance, in-memory layer of the model matrix. It is used specifically by the `/api/models/local` and `/api/models/install` REST endpoints.

### 4.1 Initialization and Disk Recovery

```python
def __init__(
    self,
    ollama_base_urls: List[str],
    cache_dir: Path,
    hardware_profile: Optional[Any] = None
):
    self.ollama_urls = ollama_base_urls
    self.cache_dir = cache_dir
    self.cache_dir.mkdir(parents=True, exist_ok=True)
    self._state = CatalogState(local_instance=ollama_base_urls[0] if ollama_base_urls else "http://localhost:11435")
    self._state_file = cache_dir / "catalog_state.json"
    self._load_from_disk()
```

On construction, the service immediately attempts to load persisted state from `{cache_dir}/catalog_state.json`. This means:

- **Cold start with existing cache:** The service is immediately operational with the last-known model list.
- **Cold start, no cache file:** `_state` remains the default empty `CatalogState`.
- **Corrupt cache file:** A `json.JSONDecodeError`, `KeyError`, or `ValueError` resets to a clean `CatalogState` rather than crashing.

The `cache_dir` is created with `parents=True, exist_ok=True`, so no pre-existing directory structure is required.

The `hardware_profile` parameter is reserved for future hardware-aware scheduling (e.g., automatically excluding `DEEP` models when VRAM is under a threshold). It has no effect in the current version.

### 4.2 Security: Model Name Validation

```python
MODEL_NAME_PATTERN = re.compile(
    r'^[a-z0-9][a-z0-9_.-]*(/[a-z0-9][a-z0-9_.-]*)?(:[a-z0-9_.-]+)?$'
)
MAX_MODEL_NAME_LENGTH = 128

def _validate_model_name(self, model_name: str) -> str:
    if not model_name:
        raise ValueError("Model name cannot be empty")
    if len(model_name) > self.MAX_MODEL_NAME_LENGTH:
        raise ValueError(f"Model name exceeds max length of {self.MAX_MODEL_NAME_LENGTH}")
    if not self.MODEL_NAME_PATTERN.match(model_name):
        raise ValueError(f"Invalid model name format: {model_name}")
    if '..' in model_name or model_name.startswith('/'):
        raise ValueError("Path traversal not allowed")
    return model_name
```

The validation enforces all of the following simultaneously:

| Guard | Threat blocked |
|-------|----------------|
| Empty check | Null/empty injection |
| 128-character limit | Buffer overflow, DoS via large key |
| Regex `^[a-z0-9]...` | Shell metacharacters (`;`, `$`, `` ` ``, `&`, `\|`, `>`, `<`) |
| Regex allows `/` only once (namespace) | Path traversal via repeated slashes |
| `..` check | Classic `../../etc/passwd` path traversal |
| `startswith('/')` check | Absolute path injection |

Valid examples: `llama3`, `llama3:8b`, `namespace/model:tag`, `qwen2.5:14b`

Invalid examples (all raise `ValueError`): `; rm -rf /`, `../etc/passwd`, `$(whoami)`, `MODEL WITH SPACES`, `A` (uppercase)

### 4.3 Fetching Local Models — Parallel with Semaphore

```python
async def get_local_models(self, use_cache: bool = True) -> List[LocalModel]:
    if use_cache and self._is_cache_valid():
        return list(self._state.local_models.values())          # O(1) dict → list

    tasks = [self._fetch_from_server(url) for url in self.ollama_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    ...
```

All configured Ollama URLs are fetched **concurrently** using `asyncio.gather`. Individual server failures (network timeout, HTTP error) are caught and returned as exceptions; the gather continues for all other servers.

**Within each server fetch:**

```python
semaphore = asyncio.Semaphore(5)   # At most 5 concurrent /api/show calls per server

async def fetch_model_details(model_data):
    async with semaphore:
        return await self._parse_model(model_data, base_url, session)
```

The semaphore prevents flooding a single Ollama server with dozens of simultaneous `/api/show` requests when a large number of models are installed. The limit of **5 concurrent detail fetches** balances speed against server load.

**Per-request timeouts:**

```python
timeout = aiohttp.ClientTimeout(total=10, connect=5)    # /api/tags
...
timeout=aiohttp.ClientTimeout(total=3)                   # /api/show per model
```

The detail fetch is deliberately short (3 seconds) — `_parse_model` uses the data from `/api/show` for rich metadata but degrades gracefully if the endpoint times out (the model is still added with `detail_data = {}`).

### 4.4 Parsing Individual Models

`_parse_model` calls `_validate_model_name` before any processing, ensuring no downstream code ever sees a model name that wasn't validated.

```python
return LocalModel(
    id             = f"local:{model_name}",
    name           = model_name.split(":")[0],
    tag            = model_name.split(":")[-1] if ":" in model_name else "latest",
    tier           = self._determine_tier(param_size),
    size_bytes     = model_data.get("size", 0),
    quantization   = details.get("quantization_level", "unknown"),
    parameter_size = param_size,
    family         = details.get("family", "unknown"),
    context_length = self._extract_context_length(detail_data),
    capabilities   = self._extract_capabilities(detail_data),
    installed_at   = datetime.fromisoformat(model_data["modified_at"]...),
    status         = ModelStatus.HEALTHY
)
```

A `ValueError`, `KeyError`, or `TypeError` during parsing returns `None`, which is filtered out by the calling gather loop. This makes the entire ingestion pipeline tolerant of malformed responses from non-standard Ollama builds.

### 4.5 Context Length Extraction

```python
def _extract_context_length(self, detail: Dict[str, Any]) -> int:
    modelfile = detail.get("modelfile", "")
    for line in modelfile.split("\n"):
        if "PARAMETER" in line and "num_ctx" in line:
            try:
                return int(line.split()[-1])
            except (ValueError, IndexError):
                pass

    family = detail.get("details", {}).get("family", "").lower()
    defaults = {"llama": 4096, "mistral": 32768, "qwen": 32768, "gemma": 8192}
    return defaults.get(family, 4096)
```

Priority:
1. **Explicit modelfile `PARAMETER num_ctx`** — The most reliable source; set by the user when creating a custom Modelfile.
2. **Family-based default** — Falls back to well-known values for common model families.
3. **Universal default of 4096** — Returned when the family is unrecognized.

### 4.6 Capability Extraction

```python
def _extract_capabilities(self, detail: Dict[str, Any]) -> List[str]:
    caps = []
    family = detail.get("details", {}).get("family", "").lower()
    name   = detail.get("name", "").lower()

    if "coder" in name or "code" in family:
        caps.append("coding")
    if "vision" in name or "vl" in name:
        caps.append("vision")
    if "tool" in name:
        caps.append("tool_use")

    return caps
```

Capabilities are extracted by keyword matching against the model name and family. This is a heuristic approach; it correctly identifies common naming conventions like `deepseek-coder`, `llava` (vision-language), and `qwen2.5-vl`. More precise detection can be provided by an operator via the `ModelMetadata` admin UI.

### 4.7 Cache TTL and Validity

```python
CACHE_TTL_SECONDS = 300  # 5 minutes

def _is_cache_valid(self) -> bool:
    if not self._state.last_local_sync:
        return False
    age = (datetime.utcnow() - self._state.last_local_sync).total_seconds()
    return age < self.CACHE_TTL_SECONDS
```

The in-memory cache is valid for **5 minutes** after the last sync. A call to `get_local_models(use_cache=True)` within this window returns immediately from `self._state.local_models` — a pure dict-to-list conversion with O(n) on the output only; the lookup itself is O(1) per item.

After 5 minutes, the next call triggers a full parallel re-fetch from all configured Ollama URLs.

Setting `use_cache=False` forces an immediate re-fetch regardless of age. The admin UI's "Refresh Models" button uses this path.

### 4.8 Atomic Disk Persistence

```python
async def _persist_to_disk(self) -> None:
    temp_file = self._state_file.with_suffix('.tmp')
    try:
        async with aiofiles.open(temp_file, 'w') as f:
            await f.write(json.dumps(self._state.to_dict(), default=str, indent=2))
        temp_file.replace(self._state_file)           # atomic rename
    except Exception:
        if temp_file.exists():
            temp_file.unlink()
```

The write is **atomic** via a write-to-temp-then-rename pattern:

1. Write complete JSON to `catalog_state.tmp`
2. Rename (atomic on POSIX) to `catalog_state.json`

If the process crashes between steps 1 and 2, the `.tmp` file is cleaned up on the next successful write. The `.json` file is never partially written. This means a crash mid-write never corrupts the on-disk state.

The `default=str` argument to `json.dumps` ensures that any unexpected non-serializable types (e.g., a stray `datetime` not caught by `to_dict`) are converted to their string representation rather than raising `TypeError`.

### 4.9 O(1) Lookup Methods

```python
def get_model_by_id(self, model_id: str) -> Optional[LocalModel]:
    return self._state.local_models.get(model_id)   # O(1) dict lookup

def get_models_by_tier(self, tier: ModelTier) -> List[LocalModel]:
    return [m for m in self._state.local_models.values() if m.tier == tier]  # O(n)

def get_models_by_capability(self, capability: str) -> List[LocalModel]:
    return [m for m in self._state.local_models.values() if capability in m.capabilities]  # O(n)

def update_model_metrics(self, model_id: str, metrics: PerformanceMetrics) -> None:
    if model_id in self._state.local_models:
        self._state.local_models[model_id].metrics = metrics   # O(1) dict lookup + field set
```

`get_model_by_id` is constant-time. Tier and capability filters are linear in the number of local models (O(n)), which is acceptable given typical catalog sizes of tens to hundreds of models. The test in `tests/test_catalog_service.py` verifies that 1,000 repeated `get_model_by_id` calls complete in under 100 ms total (≈100 µs/call).

---

## 5. Database-Level Ingestion Pipeline — fetch_and_update_models

**File:** `app/crud/server_crud.py`, function `fetch_and_update_models`

This function is the source of truth for `OllamaServer.available_models`. It is called by `refresh_all_server_models`, which is called by both the background task and the startup sequence.

### 5.1 Ollama Protocol Path

```
GET {server.url}/api/tags
  → data["models"] list
  → for each model: sanitize → build safe_model dict
  → server.available_models = [safe_model, ...]
```

The function uses a short-lived `httpx.AsyncClient` (not the long-lived app-level one) with explicit timeouts:

```python
timeout = httpx.Timeout(30.0, connect=10.0)
```

`follow_redirects=False` is deliberate: redirect following could be abused to bypass the `_is_safe_url` check by redirecting to a blocked internal address.

### 5.2 vLLM (OpenAI-Compatible) Protocol Path

```
GET {server.url}/v1/models
  → data["data"] list
  → for each model: sanitize → build safe_model dict (with size=0, digest=model_id)
  → server.available_models = [safe_model, ...]
```

Because the vLLM `/v1/models` response does not include file sizes or detailed parameter metadata, the following fields are set to fixed sentinel values:

| Field | vLLM value | Reason |
|-------|-----------|--------|
| `size` | `0` | Not available from OpenAI-compatible API |
| `digest` | model ID string | Used as a unique identifier stand-in |
| `parameter_size` | `"N/A"` | Not provided |
| `quantization_level` | `"N/A"` | Not provided |
| `format` | `"vllm"` | Distinguishes vLLM-sourced entries |
| `modified_at` | UTC epoch of `model["created"]` | Unix timestamp converted to ISO 8601 |

The `family` field is extracted heuristically by taking the first segment before the first `-` in the model ID, e.g., `"meta-llama--Llama-2-7b-chat-hf"` → `family = "meta"`.

### 5.3 Security Sanitization at Ingestion

Every field received from a remote API is sanitized before storage. This is defense-in-depth: even if a malicious or misconfigured Ollama server returns unexpected values, they cannot propagate into the database in a harmful form.

| Field | Sanitization applied |
|-------|---------------------|
| `name` (Ollama) | `re.sub(r'[^\w\.\-:@]', '', name)[:256]` |
| `model_id` (vLLM) | `re.sub(r'[^\w\.\-:/]', '', model_id)[:256]` |
| `family` (vLLM) | `re.sub(r'[^\w\.\-]', '', family)[:64]` |
| `size` | Cast to `int`; defaults to `0` on error |
| `modified_at` | Must be `str`; truncated to 64 chars |
| `digest` | `re.sub(r'[^\w:]', '', digest)[:128]` |
| `parent_model` | `str(...)[:128]` |
| `format` | `str(...)[:64]` |
| `family` (Ollama details) | `str(...)[:64]` |
| `families` array | Each element `str(f)[:64]`; array capped at 10 elements |
| `parameter_size` | `str(...)[:32]` |
| `quantization_level` | `str(...)[:32]` |

### 5.4 Hard Caps and DoS Prevention

```python
if len(models) > 10000:
    logger.warning(f"Truncating model list from {len(models)} to 10000 for server {server.name}")
    models = models[:10000]
```

A single server cannot inject more than **10,000 model entries**. Without this cap, a compromised server response could cause unbounded memory allocation and a potentially enormous JSON blob to be stored in SQLite.

Secondary caps downstream:
- `get_all_available_model_names`: result capped at 10,000
- `get_all_models_grouped_by_server`: per-server capped at 5,000
- `get_active_models_all_servers`: iterates `available_models[:100]` per server

### 5.5 Commit and Error Recording

**On success:**

```python
server.available_models    = models
server.models_last_updated = datetime.datetime.utcnow()
server.last_error          = None
await db.commit()
await db.refresh(server)
```

The `last_error` field is explicitly cleared so the admin UI can show a healthy indicator after a previously failed server recovers.

**On HTTP error or unexpected exception:**

```python
server.last_error          = error_msg   # truncated to 512 chars
server.available_models    = None
await db.commit()
```

Setting `available_models = None` (rather than `[]`) allows the smart routing layer to distinguish "we haven't fetched yet" from "we fetched and found nothing."

---

## 6. Automated Refresh Background Task

### 6.1 periodic_model_refresh Loop

**File:** `app/main.py`

```python
async def periodic_model_refresh(app: FastAPI) -> None:
    while True:
        try:
            app_settings: AppSettingsModel = app.state.settings
            interval_minutes = app_settings.model_update_interval_minutes
            interval_seconds = interval_minutes * 60

            logger.info(f"Next model refresh in {interval_minutes} minutes.")
            await asyncio.sleep(interval_seconds)        # Non-blocking sleep

            logger.info("Running periodic model refresh for all servers...")
            async with AsyncSessionLocal() as db:
                results = await server_crud.refresh_all_server_models(db)

            logger.info(
                f"Model refresh completed: {results['success']}/{results['total']} servers updated successfully"
            )
            if results['failed'] > 0:
                logger.warning(f"{results['failed']} server(s) failed to update:")
                for error in results['errors']:
                    logger.warning(f"  - {error['server_name']}: {error['error']}")

        except asyncio.CancelledError:
            logger.info("Periodic model refresh task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in periodic model refresh: {e}", exc_info=True)
            # Loop continues — a single refresh failure does not stop the background task
```

Key design decisions:

- **Sleep-first pattern:** The interval sleep comes *before* the refresh call. This means the first automatic refresh after startup happens `interval_minutes` after startup — not immediately. The startup initial refresh (§6.3) covers the "fresh data on boot" requirement.
- **Live interval reads:** `app.state.settings` is read inside the loop on every iteration. If an administrator changes `model_update_interval_minutes` in the Settings UI, the new value takes effect at the *next* iteration without any restart.
- **Exception isolation:** Non-`CancelledError` exceptions are caught and logged; the loop continues. A transient database connection failure or a bug in the refresh logic does not permanently stop the background task.
- **Cancellation handling:** `asyncio.CancelledError` is cleanly handled with a `break`, allowing graceful shutdown without an unhandled exception being propagated.

### 6.2 refresh_all_server_models Orchestrator

**File:** `app/crud/server_crud.py`

```python
async def refresh_all_server_models(db: AsyncSession) -> dict:
    servers = await get_servers(db)
    active_servers = [(s.id, s.name) for s in servers if s.is_active]

    results = {"total": len(active_servers), "success": 0, "failed": 0, "errors": []}

    for server_id, server_name in active_servers:
        result = await fetch_and_update_models(db, server_id)
        if result["success"]:
            results["success"] += 1
        else:
            results["failed"] += 1
            results["errors"].append({
                "server_id":   server_id,
                "server_name": server_name,
                "error":       result["error"][:512] if result["error"] else "Unknown error"
            })

    return results
```

Note: Servers are fetched **sequentially** (one `await` per server in the for loop), not concurrently. This is intentional — it avoids database contention and thundering-herd issues when many servers are configured. For fleets where this is too slow, parallel fetching can be achieved by wrapping each `fetch_and_update_models` call in a task and gathering results.

The function returns a structured dict that is logged at the `INFO` level on success and `WARNING` level per failed server.

### 6.3 Startup Initial Refresh

**File:** `app/main.py`, inside the `lifespan` async context manager:

```python
logger.info("Performing initial model refresh on startup...")
async with AsyncSessionLocal() as db:
    initial_results = await server_crud.refresh_all_server_models(db)
logger.info(f"Initial model refresh: {initial_results['success']}/{initial_results['total']} servers updated")
```

This runs **after** the database is initialized, settings are loaded, and the admin user is created, but **before** `yield` (i.e., before the server begins accepting requests). This guarantees that:

1. The proxy's model catalog is populated when the first request arrives.
2. Smart routing works correctly from the first request without waiting for the background task's first sleep interval.

If a backend server is unreachable at startup, `fetch_and_update_models` records the error in `server.last_error` but does not block startup. The background task will retry on its next interval.

### 6.4 Graceful Shutdown and Cancellation

**File:** `app/main.py`, shutdown section of `lifespan`:

```python
if hasattr(app.state, 'refresh_task'):
    app.state.refresh_task.cancel()
    try:
        await app.state.refresh_task
    except asyncio.CancelledError:
        pass
```

The `asyncio.CancelledError` propagated from `task.cancel()` is caught and silenced. The `periodic_model_refresh` function itself also catches it (with `break`), so the exception is handled at both levels. This ensures clean shutdown without spurious error log entries.

### 6.5 Live Interval Updates

Because the background task reads `app.state.settings.model_update_interval_minutes` at the top of each loop iteration, an administrator can effectively change the refresh interval at runtime:

1. Navigate to **Settings → General**
2. Update the **Model Update Interval** field
3. Save

The *currently sleeping* iteration will complete its original sleep, then pick up the new value. The maximum additional latency before the new interval takes effect is one complete old interval.

---

## 7. Auto-Routing Intelligence — _select_auto_model

**File:** `app/api/v1/routes/proxy.py`

`_select_auto_model` is called when the API consumer sets `"model": "auto"` in their request body. It analyzes the request content and available models to select the best one.

### 7.1 Input Signal Extraction

Three signals are extracted from the request body before any filtering:

**Signal 1: Has images?**
```python
has_images = "images" in body and body["images"]
```
Checks for the `images` field (used by Ollama's multimodal endpoints). Truthy if the list is non-empty.

**Signal 2: Contains code?**
```python
code_keywords = ["def ", "class ", "import ", "const ", "let ", "var ",
                 "function ", "public static void", "int main("]
contains_code = any(kw.lower() in prompt_content.lower() for kw in code_keywords)
```
The prompt is extracted from either `body["prompt"]` (generate endpoint) or the last message's `content` field (chat endpoint). If that `content` is a list (multimodal message format), only the **first text part** (`type == "text"`) is scanned; additional text items are ignored.

**Signal 3: Fast model requested?**
```python
body.get("options", {}).get("fast_model")
```
A non-standard extension: API consumers can set `"options": {"fast_model": true}` to request a lower-latency model.

### 7.2 Image-Support Filter

```python
if has_images:
    candidate_models = [m for m in candidate_models if m.supports_images]
```

If the request contains images, only models with `ModelMetadata.supports_images = True` are considered. If *no* models have image support configured, the filter produces an empty list, which falls back to the full available_metadata list (see §7.6).

### 7.3 Code-Keyword Filter

```python
if contains_code:
    code_models = [m for m in candidate_models if m.is_code_model]
    if code_models:
        candidate_models = code_models
```

Unlike the image filter, the code filter only narrows the candidate set **if at least one code model is found**. If no code model is available, the original candidate set (post-image-filter) is preserved. This prevents a "no models found" error when a user sends a code snippet but hasn't configured any code-specific models.

### 7.4 Fast-Model Option Filter

```python
if body.get("options", {}).get("fast_model"):
    fast_models = [m for m in candidate_models if m.is_fast_model]
    if fast_models:
        candidate_models = fast_models
```

Same soft-filter pattern as code: only narrows if fast models are available.

### 7.5 Priority Ordering and Final Selection

```python
# candidate_models is already sorted by priority ASC (from get_all_metadata ORDER BY priority)
best_model = candidate_models[0]
logger.info(f"Auto-routing selected model '{best_model.model_name}' with priority {best_model.priority}.")
return best_model.model_name
```

The `available_metadata` list returned by `get_all_metadata(db)` is sorted `ORDER BY priority ASC, model_name ASC` at the database level. All filter operations preserve order (Python list comprehensions maintain insertion order). The `[0]` selection therefore always picks the highest-priority surviving candidate. Within the same priority level, alphabetical sort by `model_name` provides a stable tie-break.

### 7.6 Fallback Strategy

```python
if not candidate_models:
    logger.warning("Auto-routing: No models matched the request criteria. Falling back to the highest priority model available.")
    candidate_models = available_metadata

if not candidate_models:
    return None
```

Two-level fallback:
1. **Criteria fallback:** If all filters produce an empty set, reset to `available_metadata` (all models with any metadata, sorted by priority).
2. **Complete failure:** If there are no metadata-configured models available at all, return `None`.

When `None` is returned, the proxy raises HTTP `503 Service Unavailable`:

```python
if not chosen_model_name:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Auto-routing could not find an available and suitable model."
    )
```

---

## 8. Smart Model Routing — get_servers_with_model

**File:** `app/crud/server_crud.py`

Once a model name is known (either from the request or from auto-routing), `get_servers_with_model` finds which active servers host that model.

### 8.1 Exact Match

```python
available_model_name == model_name
```

e.g. `"llama3:8b"` matches `"llama3:8b"`. This is the highest-confidence match.

### 8.2 Prefix Match

```python
available_model_name.startswith(f"{model_name}:")
```

e.g. `"llama3"` matches `"llama3:8b"`, `"llama3:latest"`. This handles the common case where a consumer requests a model without specifying a tag — they get any installed version.

### 8.3 vLLM Substring Match

```python
server.server_type == 'vllm' and model_name in available_model_name
```

vLLM model IDs can be paths like `"models--meta-llama--Llama-2-7b-chat-hf"`. A consumer requesting `"Llama-2-7b"` is matched by substring. This match is only applied to vLLM servers to avoid false positives with Ollama models.

### 8.4 Fallback to Round-Robin

```python
if servers_with_model:
    candidate_servers = servers_with_model
else:
    logger.warning(
        f"Model '{model_name}' not found in any server's catalog. "
        f"Falling back to round-robin across all {len(servers)} active server(s)."
    )
    # candidate_servers remains the full active servers list
```

If a model is not found in any server's catalog, the proxy does *not* fail immediately. Instead, it falls back to round-robin across all active servers. This handles edge cases where:
- The model was installed after the last catalog refresh
- The server's `/api/tags` response was temporarily unavailable during the last refresh
- The model name in the request uses a different format than stored in `available_models`

The request may still fail at the backend, but this gives it the best chance of succeeding.

---

## 9. Federated Model View — GET /api/tags

**File:** `app/api/v1/routes/proxy.py`, `federate_models` handler

This endpoint provides a unified, Ollama-compatible `/api/tags` response that aggregates all models from all active backends. It is consumed by Ollama-compatible clients expecting to enumerate available models.

### 9.1 Deduplication by Model Name

Models from multiple servers are deduplicated by name in a dict (`all_models`). If the same model name appears on two servers, the **last-seen** entry wins. The order is determined by the insertion order of the server list returned by `get_servers(db)` (sorted by `created_at DESC`).

### 9.2 The Synthetic "auto" Model Entry

```python
all_models["auto"] = {
    "name":        "auto",
    "model":       "auto",
    "modified_at": ...,
    "digest":      "auto-digest-placeholder",
    "details": {
        "family":           "auto",
        "families":         ["auto"],
        "parameter_size":   "varies",
        "quantization_level": "varies"
    }
}
```

The `"auto"` entry is injected into the federated model list **after** all real models. This makes it visible to any Ollama-compatible client as a selectable model. When a client sends a request with `"model": "auto"`, the proxy intercepts it and routes through `_select_auto_model` rather than forwarding to a backend.

The `"Proxy Features"` group in `get_all_models_grouped_by_server` serves the same purpose for the admin UI's model picker dropdowns.

---

## 10. Retry Engine — retry_with_backoff

**File:** `app/core/retry.py`

### 10.1 RetryConfig Fields and Defaults

```python
@dataclass
class RetryConfig:
    max_retries: int = 5              # Maximum retry attempts after the first failure
    total_timeout_seconds: float = 2.0 # Hard ceiling on total time across all attempts
    base_delay_ms: int = 50           # Base exponential backoff delay in milliseconds
```

These defaults favor **resilience** while keeping retries bounded: exponential backoff fits five retries inside roughly two seconds, so transient cold starts get another chance without hammering the backend.

All three values are configurable through the admin Settings UI (`AppSettingsModel`) and take effect immediately on the next request without a restart.

### 10.2 Exponential Backoff Formula

```
delay_ms = base_delay_ms × (2 ^ attempt_index)

attempt 0 → 1st try  (no delay before first attempt)
attempt 1 → 2nd try  delay = 50 × 2^0 = 50 ms
attempt 2 → 3rd try  delay = 50 × 2^1 = 100 ms
attempt 3 → 4th try  delay = 50 × 2^2 = 200 ms
attempt 4 → 5th try  delay = 50 × 2^3 = 400 ms
attempt 5 → 6th try  delay = 50 × 2^4 = 800 ms
```

With default settings (`max_retries=5`, `base_delay_ms=50`):
- Maximum cumulative delay = 50 + 100 + 200 + 400 + 800 = 1,550 ms
- This fits within the `total_timeout_seconds=2.0` budget, leaving room for request/response time

The actual sleep time is `min(calculated_delay, remaining_time_in_budget)`, ensuring the total budget is never exceeded.

A micro-optimization: if the calculated delay is ≤ 1 ms, the sleep is skipped entirely:

```python
if actual_delay > 0.001:
    await asyncio.sleep(actual_delay)
```

### 10.3 Total Timeout Budget Enforcement

The `total_timeout_seconds` check occurs **at the start of each attempt**, before the actual call:

```python
elapsed = time.time() - start_time
if elapsed >= config.total_timeout_seconds:
    break
```

This means that even if `max_retries` allows more attempts, the budget check can cut the retry loop short. The effective number of attempts = `min(max_retries + 1, attempts_fitting_within_budget)`.

### 10.4 RetryResult Structure

```python
@dataclass
class RetryResult:
    success: bool
    result: Optional[any] = None      # The return value of the wrapped function
    attempts: int = 0                 # Total attempts made (including the initial try)
    total_duration_ms: float = 0.0    # Wall-clock time for all attempts combined
    errors: List[str] = None          # Per-attempt error messages (truncated to 200 chars each)
```

The calling code checks `retry_result.success` before accessing `retry_result.result`. On failure, `retry_result.errors` contains the per-attempt error messages for diagnostic logging.

---

## 11. Security Hardening

### 11.1 SSRF Prevention — _is_safe_url

**File:** `app/crud/server_crud.py`

Server-Side Request Forgery (SSRF) is prevented by validating every server URL before any network request is made. The check applies at:
- **Server creation** (`create_server`)
- **Server update** (`update_server`)
- **Every model fetch** (`fetch_and_update_models` re-validates at fetch time)
- **Health checks** (`check_server_health`)

```python
def _is_safe_url(url: str) -> bool:
    parsed = urlparse(str(url))

    # 1. Only http/https allowed
    if parsed.scheme not in ('http', 'https'):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # 2. Block localhost by name
    if hostname.lower() in ('localhost', 'localhost.localdomain'):
        return False

    # 3. DNS resolution check
    ip_str = socket.gethostbyname(hostname)
    ip_obj = ipaddress.ip_address(ip_str)

    # 4. Block loopback (127.0.0.0/8, ::1)
    if ip_obj.is_loopback:
        return False

    # 5. Block AWS metadata endpoint (169.254.169.254)
    if str(ip_obj) == "169.254.169.254":
        return False

    # 6. Block 0.0.0.0
    if str(ip_obj) == "0.0.0.0":
        return False

    return True
```

Note: Private IP ranges (RFC 1918: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) are **intentionally allowed**, because legitimate local Ollama servers running on a LAN are a primary use case.

DNS failure (`socket.gaierror`) is silently permitted — the request is allowed to proceed and will fail naturally at the HTTP layer. Blocking on DNS failure would prevent adding servers with temporarily unreachable hostnames.

### 11.2 Injection Prevention at Every Layer

| Layer | Protection |
|-------|-----------|
| `CatalogService._validate_model_name` | Regex + path traversal check before any processing |
| `fetch_and_update_models` | `re.sub` sanitization on all string fields from API responses |
| `get_servers_with_model` | `re.sub(r'[^\w\.\-:@]', '', model_name)[:256]` before comparison |
| `get_all_available_model_names` | Model name truncated to 256 chars |
| `pull_model_on_server` | Regex check `r'^[\w\.\-:@]+$'` before forwarding to Ollama |
| Error messages stored in `server.last_error` | Truncated to 512 chars |
| `RetryResult.errors` | Each message truncated to 200 chars |

### 11.3 Model List Size Caps

| Location | Cap |
|----------|-----|
| `fetch_and_update_models` | 10,000 models per server |
| `get_all_available_model_names` | 10,000 unique names total |
| `get_all_models_grouped_by_server` | 5,000 per server |
| `get_active_models_all_servers` | 100 entries from `available_models` per server |

### 11.4 Error Message Truncation

All error messages written to the database or logs are length-limited:

| Location | Limit |
|----------|-------|
| `server.last_error` | 512 chars |
| `results["errors"][*]["error"]` | 512 chars |
| `RetryResult.errors` per entry | 200 chars |
| `check_server_health` reason | 256 chars |
| Exception string in health check | 256 chars |

---

## 12. Configuration Reference

All configurable values reside in `AppSettingsModel` (`app/schema/settings.py`) and are persisted in the `app_settings` SQLite table. They can be changed live through the **Settings** admin UI.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_update_interval_minutes` | `int` | `10` | How often the background task refreshes all server model lists. Minimum effective value is 1 minute. |
| `max_retries` | `int` | `5` | Maximum retry attempts per backend request. Range: 0–20. |
| `retry_total_timeout_seconds` | `float` | `2.0` | Hard wall-clock budget for all retry attempts. Range: 0.1–30.0. |
| `retry_base_delay_ms` | `int` | `50` | Base delay for exponential backoff. Range: 1–5,000 ms. |

---

## 13. REST API Catalog Endpoints

**File:** `app/routes/catalog_routes.py`

These endpoints use the `CatalogService` in-memory layer (not the SQLite `available_models` column). They are mounted without a prefix, so they appear at the root path level.

### GET /api/models/local

Returns locally installed models from the in-memory catalog with optional filtering.

**Authentication:** Requires a valid API key (or admin session) via `get_current_user`.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `tier` | `str` (optional) | Filter by tier value: `"nano"`, `"fast"`, `"balanced"`, `"deep"` |
| `capability` | `str` (optional) | Filter by capability string: `"coding"`, `"vision"`, `"tool_use"` |

**Response:**

```json
{
  "data": [
    {
      "id": "local:llama3:8b",
      "name": "llama3",
      "tag": "8b",
      "tier": "fast",
      "source": "local",
      "size_bytes": 4920000000,
      "size_gb": 4.58,
      "quantization": "Q4_K_M",
      "parameter_size": "8B",
      "family": "llama",
      "context_length": 4096,
      "capabilities": [],
      "installed_at": "2025-11-01T12:00:00",
      "last_used": "2026-03-06T03:00:00",
      "metrics": {
        "first_token_ms": null,
        "tokens_per_second": null,
        "benchmark_score": null,
        "timeout_rate": 0.0,
        "error_rate": 0.0,
        "last_benchmark_at": null
      },
      "status": "healthy",
      "fits_hardware": true
    }
  ],
  "meta": {
    "cache_status": "hit"
  }
}
```

`meta.cache_status` is `"hit"` when the response came from the 5-minute in-memory cache, or `"miss"` when a live fetch from Ollama was performed.

**Performance target:** <50 ms for cache hits (pure dict iteration); <5 s for cache misses with 5 servers.

### POST /api/models/install

Queues a model for installation. Returns a websocket channel name for progress tracking.

**Authentication:** Requires a valid API key.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_name` | `str` | Model to install. Validated through `_validate_model_name`. |

**Response:**

```json
{
  "status": "queued",
  "model": "llama3:8b",
  "websocket_channel": "install-progress:llama3:8b"
}
```

*Note:* The actual pull operation and WebSocket streaming are handled by the admin UI routes, not this endpoint. This endpoint validates the model name and returns the channel to listen on.

**Rate limiting note:** The endpoint comment documents an intent of 5 calls/hour, which is enforced by the Redis rate limiter when configured.

---

## 14. End-to-End Data Flow Diagrams

### 14.1 Startup Refresh Flow

```
FastAPI lifespan starts
        │
        ▼
  init_db()
  run_all_migrations()
  Base.metadata.create_all()
        │
        ▼
  Load AppSettings from DB
        │
        ▼
  create_initial_admin_user()
        │
        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │         INITIAL MODEL REFRESH                               │
  │                                                             │
  │  refresh_all_server_models(db)                              │
  │    │                                                        │
  │    ├─► fetch_and_update_models(db, server_id=1)             │
  │    │     ├─► _is_safe_url(server.url)  [SSRF check]         │
  │    │     ├─► GET /api/tags  OR  GET /v1/models              │
  │    │     ├─► Sanitize all fields                            │
  │    │     ├─► Truncate to 10,000 models                      │
  │    │     └─► server.available_models = [...]; db.commit()   │
  │    │                                                        │
  │    ├─► fetch_and_update_models(db, server_id=2)             │
  │    └─► ...                                                  │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
  asyncio.create_task(periodic_model_refresh(app))
        │
        ▼
  yield  ←──── Server begins accepting requests
```

### 14.2 Periodic Background Refresh Flow

```
periodic_model_refresh loop:

  ┌──────────────────────────────────────────────────────────────┐
  │  READ app.state.settings.model_update_interval_minutes       │
  │         (live value — picks up admin UI changes)             │
  └──────────────────────────────────────────────────────────────┘
        │
        ▼
  asyncio.sleep(interval_seconds)
        │
        ▼
  refresh_all_server_models(db)
        │
        ├─► Per active server: fetch_and_update_models()
        │     ├─ Success → update available_models, clear last_error
        │     └─ Failure → set last_error, clear available_models
        │
        ▼
  LOG: "N/M servers updated successfully"
  If failures: LOG WARNING per failed server
        │
        ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  LOOP (back to sleep)                                        │
  └──────────────────────────────────────────────────────────────┘
```

### 14.3 API Request Auto-Routing Flow

```
POST /api/generate  {"model": "auto", "prompt": "def quicksort..."}
        │
        ▼
  proxy_ollama()
        │
        ├─► model_name == "auto"?  YES
        │         │
        │         ▼
        │   _select_auto_model(db, body)
        │         │
        │         ├─► Extract signals:
        │         │     has_images = False
        │         │     contains_code = True  (keyword "def ")
        │         │     fast_model = False
        │         │
        │         ├─► get_all_metadata(db) → sorted by priority
        │         ├─► get_all_available_model_names(db)
        │         ├─► available_metadata = intersection of both
        │         │
        │         ├─► Filter: code models only (is_code_model=True)
        │         │     → [deepseek-coder:6.7b (priority=5), ...]
        │         │
        │         └─► SELECT candidate[0] = "deepseek-coder:6.7b"
        │
        ├─► model_name = "deepseek-coder:6.7b"
        │   body["model"] = "deepseek-coder:6.7b"
        │
        ▼
  get_servers_with_model(db, "deepseek-coder:6.7b")
        │
        ├─► Scan active servers' available_models
        │     server-A: has "deepseek-coder:6.7b" (exact match) ✓
        │     server-B: does not have it ✗
        │
        └─► candidate_servers = [server-A]
        │
        ▼
  _reverse_proxy(request, path, [server-A], body_bytes)
        │
        ├─► First attempt: POST server-A/api/generate
        │     → Success (HTTP 200)
        │
        └─► Return StreamingResponse to client
```

### 14.4 Smart Model Routing Decision Tree

```
Incoming request with model_name = "X"
        │
        ├─ Is model_name "auto"? ──YES──► _select_auto_model() → resolves to concrete name
        │
        ▼  (model_name is now a concrete model name)
        │
get_servers_with_model(db, "X")
        │
        ├─ For each active server S:
        │     For each model M in S.available_models:
        │
        │       M == "X"?                          → EXACT MATCH: add S, break
        │       M.startswith("X:")                 → PREFIX MATCH: add S, break
        │       S.server_type=='vllm' AND "X" in M → SUBSTRING MATCH: add S, break
        │
        ├─ servers_with_model is non-empty?
        │     YES → candidate_servers = servers_with_model
        │            (logged: "Smart routing: Found N server(s)")
        │
        │     NO  → candidate_servers = ALL active servers
        │            (logged: "Model not found, falling back to round-robin")
        │
        ▼
  _reverse_proxy(request, candidate_servers)
        │
        ├─► Pick server from candidate_servers (round-robin)
        ├─► First attempt
        │     Success → return response
        │     Failure → retry_with_backoff (up to max_retries within total_timeout)
        │                 Each retry attempt: same server
        │
        └─► If all retries fail → HTTP 502 Bad Gateway
```

---

## 15. Glossary

| Term | Definition |
|------|-----------|
| **Automated Model Matrix** | The complete subsystem responsible for discovering, classifying, caching, and routing to AI models across all configured backends. |
| **available_models** | The JSON column in `ollama_servers` DB table that stores the last-known list of models for each server. The primary data store for smart routing and the federated `/api/tags` view. |
| **auto routing** | When `"model": "auto"` is set in a request, the proxy selects the best model from `ModelMetadata` based on request content signals (images, code keywords, fast-model flag). |
| **CatalogService** | The in-memory cache layer managing `CatalogState`, used by the `/api/models/local` and `/api/models/install` endpoints. |
| **CatalogState** | The in-memory and on-disk data structure holding all `LocalModel` and `CloudModel` entries. |
| **CloudModel** | A data class describing a cloud-hosted AI model. Currently a reserved type for future integrations. |
| **fetch_and_update_models** | The core async function that fetches model lists from a single server (Ollama or vLLM) and writes the result to `OllamaServer.available_models`. |
| **federated view** | The aggregation of model lists from all active backends into a single Ollama-compatible `/api/tags` response, with deduplication and the synthetic `auto` entry. |
| **LocalModel** | A data class describing a model installed on an Ollama backend, including tier, capabilities, size, context length, and performance metrics. |
| **ModelMetadata** | The SQLite table holding administrator-curated metadata about models, used by the auto-router. Includes priority, capability flags, and image support. |
| **ModelTier** | A classification of a model's hardware requirements: `NANO` (≤3B), `FAST` (≤8B), `BALANCED` (≤14B), `DEEP` (>14B). |
| **periodic_model_refresh** | The background asyncio task that calls `refresh_all_server_models` on a configurable interval. |
| **refresh_all_server_models** | The orchestrator that iterates active servers and calls `fetch_and_update_models` for each one. |
| **RetryConfig** | Configuration for the exponential backoff retry engine: `max_retries`, `total_timeout_seconds`, `base_delay_ms`. |
| **smart routing** | The behavior where a request specifying a concrete model name is automatically directed to a server known to have that model, via `get_servers_with_model`. |
| **SSRF** | Server-Side Request Forgery. Prevented by `_is_safe_url` blocking localhost, loopback IPs, AWS metadata endpoints, and non-http/https schemes. |
| **vLLM** | An OpenAI-compatible inference backend. The proxy handles vLLM servers via the `/v1/models` and `/v1/chat/completions` endpoints, translating responses to Ollama's API format. |
