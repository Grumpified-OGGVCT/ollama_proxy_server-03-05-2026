YYYY-MM-DD - 2026-03-06
Title: KV Cache & VRAM calculation
Context: Adding KV cache calculations for accurate VRAM requirements when proxying to Ollama servers.
Learning: Disk size is not VRAM size; a 14B model can use over 10GB of VRAM with a large context.
Evidence: OOM (Out Of Memory) crashes when VRAM estimates ignored context window KV cache sizes.
Action: Implemented accurate estimates considering context lengths.

YYYY-MM-DD - 2026-03-06
Title: vLLM vs Ollama Concurrency
Context: Both vLLM and Ollama were being sent equal traffic for concurrent requests.
Learning: vLLM can handle continuous batching and many requests, while Ollama struggles past a handful.
Evidence: System hung due to overloading Ollama instead of using the robust vLLM instance.
Action: Gave vLLM servers a priority weight of 2.0 when choosing where to route requests.

YYYY-MM-DD - 2026-03-06
Title: Speculative Decoding and O(1) Context
Context: Added predictive models and optimization architectures.
Learning: Memory mapping and O(1) context constraints allow predictable performance regardless of session sizes.
Evidence: OOM (Out Of Memory) crashes and slowdowns on long-running contexts prevented.
Action: Implemented HTTP pooling, memory mapping, and adaptive batching.

YYYY-MM-DD - 2026-03-06
Title: Architectural Enums Documentation
Context: Explicit mapping of Cloud targets inside Catalog objects.
Learning: Python Enum classes required hard-coding to override default 'Local/Cloud' fallbacks to properly target OpenRouter and specific Cloud API variations natively.
Evidence: OpenRouter keys failed to trigger until generic `source=ModelSource.CLOUD` was patched to `source=ModelSource.OPENROUTER`.
Action: Modified explicit Matrix values matching settings mappings.
